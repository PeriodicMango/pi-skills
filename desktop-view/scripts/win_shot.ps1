param(
  [string]$Title = "",
  [int]$Pad = 0,
  [string]$Out = "",
  [switch]$List,
  [switch]$Screen
)

# Window reader / screen reporter for a Windows host. Run it through winshot.sh, which
# handles the ssh round trip and the temp paths.
#
#   -List                 dump every visible top-level window as hwnd|class|title|x,y,w,h
#                         (text only, no pixels - use this first to find the target)
#   -Title <substring>    capture that window. Matches on GetWindowText, picks the largest
#                         match if several, and prints every match.
#   -Pad <n>              add an n-pixel ring around the window, grabbed from the screen.
#                         WARNING: the ring shows whatever is stacked there, including
#                         other windows. Default 0 = the window's own pixels only.
#   -Screen               report the virtual desktop, each monitor's bounds, and this
#                         process's DPI awareness. Run this before trusting any
#                         coordinate you read elsewhere: a DPI-unaware process sees a
#                         different coordinate space than a DPI-aware one.
#
# Why PrintWindow and not CopyFromScreen: CopyFromScreen captures the composited screen, so
# whatever window is stacked on top ends up in the image. PrintWindow asks the target window
# itself, so occlusion and even off-screen placement do not matter. PW_RENDERFULLCONTENT (2)
# is required for DWM-composited windows, otherwise PrintWindow returns a blank bitmap.
#
# Known limits: menu popups, tooltips and context menus are separate top-level windows
# (capture them by their own title or class), the desktop/wallpaper is not a window, and
# minimized windows may come back blank.
#
# ASCII ONLY in this file. PowerShell 5.1 reads .ps1 as ANSI, and non-ASCII comment bytes
# can swallow the following line.

# Force UTF-8 on stdout, otherwise window titles with non-ASCII characters come back
# mojibake through ssh (PowerShell writes them in the console codepage).
[Console]::OutputEncoding = [Text.Encoding]::UTF8

if ($Out -eq "") { $Out = Join-Path $env:TEMP "winshot.png" }

Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class WinShot {
  public delegate bool EnumProc(IntPtr h, IntPtr p);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr p);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowTextW(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassNameW(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L; public int T; public int R; public int B; }
}
"@

if ($Screen) {
  Add-Type -AssemblyName System.Windows.Forms
  Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Dpi {
  [DllImport("shcore.dll")] public static extern int GetProcessDpiAwareness(IntPtr h, out int v);
}
"@
  $vs = [System.Windows.Forms.SystemInformation]::VirtualScreen
  Write-Output ("VIRTUAL|{0},{1},{2},{3}" -f $vs.Left, $vs.Top, $vs.Width, $vs.Height)
  foreach ($s in [System.Windows.Forms.Screen]::AllScreens) {
    $b = $s.Bounds
    Write-Output ("MONITOR|{0}|{1},{2},{3},{4}|primary={5}" -f $s.DeviceName, $b.X, $b.Y, $b.Width, $b.Height, $s.Primary)
  }
  $aware = -1
  try { [void][Dpi]::GetProcessDpiAwareness([System.Diagnostics.Process]::GetCurrentProcess().Handle, [ref]$aware) } catch { $aware = -1 }
  $name = switch ($aware) { 0 { "unaware" } 1 { "system" } 2 { "per-monitor" } default { "unknown" } }
  Write-Output ("DPI_AWARENESS|{0}|{1}" -f $aware, $name)
  Write-Output "NOTE|A DPI-unaware process sees a virtualized coordinate space; a per-monitor-aware one sees physical pixels. Coordinates from another program are only comparable to these if the awareness levels match."
  exit 0
}

$rows = New-Object System.Collections.ArrayList
$cb = [WinShot+EnumProc]{
  param($hw, $p)
  if ([WinShot]::IsWindowVisible($hw)) {
    $t = New-Object System.Text.StringBuilder 512
    [void][WinShot]::GetWindowTextW($hw, $t, 512)
    $c = New-Object System.Text.StringBuilder 512
    [void][WinShot]::GetClassNameW($hw, $c, 512)
    $r = New-Object WinShot+RECT
    [void][WinShot]::GetWindowRect($hw, [ref]$r)
    $w = $r.R - $r.L
    $h = $r.B - $r.T
    if ($w -ge 32 -and $h -ge 32) {
      [void]$rows.Add([pscustomobject]@{
        Hwnd = $hw.ToString(); Class = $c.ToString(); Title = $t.ToString()
        X = $r.L; Y = $r.T; W = $w; H = $h
      })
    }
  }
  return $true
}
[void][WinShot]::EnumWindows($cb, [IntPtr]::Zero)

if ($List -or $Title -eq "") {
  foreach ($r in $rows) {
    Write-Output ("{0}|{1}|{2}|{3},{4},{5},{6}" -f $r.Hwnd, $r.Class, $r.Title, $r.X, $r.Y, $r.W, $r.H)
  }
  exit 0
}

$hits = @($rows | Where-Object { $_.Title.Contains($Title) })
Write-Output ("MATCHCOUNT|" + $hits.Count)
foreach ($h in $hits) {
  Write-Output ("MATCH|{0}|{1}|{2}|{3},{4},{5},{6}" -f $h.Hwnd, $h.Class, $h.Title, $h.X, $h.Y, $h.W, $h.H)
}
if ($hits.Count -eq 0) { Write-Output "NOTFOUND"; exit 1 }

$t = $hits | Sort-Object -Property @{Expression={$_.W * $_.H}} -Descending | Select-Object -First 1
Write-Output ("CHOSEN|{0}|{1}" -f $t.Hwnd, $t.Title)

# 1) the window's own pixels
$win = New-Object System.Drawing.Bitmap $t.W, $t.H
$gw = [System.Drawing.Graphics]::FromImage($win)
$hdc = $gw.GetHdc()
$ok = [WinShot]::PrintWindow([IntPtr][int]$t.Hwnd, $hdc, 2)
$gw.ReleaseHdc($hdc)
$gw.Dispose()
Write-Output ("PRINTWINDOW|" + $ok)

# 2) optional ring from the composited screen. The window area is overwritten by the
#    PrintWindow bitmap afterwards, so an occluder cannot leak into the window itself.
$outW = $t.W; $outH = $t.H
$dstX = 0; $dstY = 0
if ($Pad -gt 0) {
  Add-Type -AssemblyName System.Windows.Forms
  $vs = [System.Windows.Forms.SystemInformation]::VirtualScreen
  $rx = [Math]::Max($t.X - $Pad, $vs.Left)
  $ry = [Math]::Max($t.Y - $Pad, $vs.Top)
  $rr = [Math]::Min($t.X + $t.W + $Pad, $vs.Left + $vs.Width)
  $rb = [Math]::Min($t.Y + $t.H + $Pad, $vs.Top + $vs.Height)
  $outW = $rr - $rx; $outH = $rb - $ry
  $dstX = $t.X - $rx; $dstY = $t.Y - $ry
  Write-Output ("RING|{0},{1},{2},{3}" -f $rx, $ry, $outW, $outH)
}

$bmp = New-Object System.Drawing.Bitmap $outW, $outH
$g = [System.Drawing.Graphics]::FromImage($bmp)
if ($Pad -gt 0) {
  $g.CopyFromScreen($rx, $ry, 0, 0, (New-Object System.Drawing.Size $outW, $outH))
}
$g.DrawImage($win, $dstX, $dstY)
$g.Dispose()
$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
$win.Dispose()

Write-Output ("SIZE|{0}x{1}|dst={2},{3}" -f $outW, $outH, $dstX, $dstY)
Write-Output ("SAVED|" + $Out)
