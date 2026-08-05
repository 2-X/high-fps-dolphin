param(
  [string]$Label    = "run",
  [string]$Speed    = "3.0",     # Dolphin EmulationSpeed; "0" = unlimited
  [string]$Affinity = "0xFFFF",  # "none" to leave Windows scheduling alone
  [string]$Priority = "High",
  [string]$Backend  = "",        # "" = use ini; else Vulkan / D3D / D3D12 / OGL
  [int]$Seconds     = 70
)

$ErrorActionPreference = 'Stop'

if (-not ("ThreadName" -as [type])) {
  Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class ThreadName {
  [DllImport("kernel32.dll", SetLastError=true)]
  public static extern IntPtr OpenThread(int access, bool inherit, uint tid);
  [DllImport("kernel32.dll", SetLastError=true)]
  public static extern bool CloseHandle(IntPtr h);
  [DllImport("kernel32.dll", CharSet=CharSet.Unicode)]
  public static extern int GetThreadDescription(IntPtr h, out IntPtr desc);
  [DllImport("kernel32.dll")]
  public static extern IntPtr LocalFree(IntPtr p);
  public static string Get(uint tid) {
    IntPtr h = OpenThread(0x0800, false, tid);       // THREAD_QUERY_LIMITED_INFORMATION
    if (h == IntPtr.Zero) return "";
    IntPtr d;
    string s = "";
    if (GetThreadDescription(h, out d) >= 0 && d != IntPtr.Zero) {
      s = Marshal.PtrToStringUni(d);
      LocalFree(d);
    }
    CloseHandle(h);
    return s == null ? "" : s;
  }
}
"@
}

function Snap($proc) {
  $proc.Refresh()
  $h = @{}
  foreach ($t in $proc.Threads) {
    try { $h[[uint32]$t.Id] = $t.TotalProcessorTime.TotalSeconds } catch {}
  }
  return $h
}

$root = "C:\Users\krisb\code\high-fps-dolphin\dolphin-bin\Dolphin-x64"
$rom  = "C:\Users\krisb\kris-documents\games\dolphin\Super Mario Sunshine (USA).rvz"
$st   = Join-Path $root "User\StateSaves\GMSE01.s02"
$logs = Join-Path $root "User\Logs"

foreach ($f in @("render_times.txt","vblank_times.txt")) {
  $p = Join-Path $logs $f
  if (Test-Path $p) { Remove-Item $p -Force }
}

$args = @("-e", "`"$rom`"", "-s", "`"$st`"", "-b", "-C", "Dolphin.Core.EmulationSpeed=$Speed")
if ($Backend -ne "") { $args += @("-v", $Backend) }
$p = Start-Process -FilePath (Join-Path $root "Dolphin.exe") -ArgumentList $args -PassThru
Write-Output "=== $Label : speed=$Speed affinity=$Affinity priority=$Priority pid=$($p.Id) ==="

Start-Sleep -Seconds 8    # boot + load savestate
$proc = Get-Process -Id $p.Id
if ($Affinity -ne "none") {
  try {
    $proc.ProcessorAffinity = [IntPtr][Convert]::ToInt64($Affinity, 16)
    $proc.PriorityClass = $Priority
  } catch { Write-Output "affinity/priority FAILED: $($_.Exception.Message)" }
}

Start-Sleep -Seconds 6    # let it settle before sampling threads
$t0 = Snap $proc
$w0 = Get-Date
Start-Sleep -Seconds $Seconds
$t1 = Snap $proc
$wall = ((Get-Date) - $w0).TotalSeconds

Write-Output "--- per-thread CPU over ${wall}s (100% = one saturated core) ---"
$rows = @()
foreach ($tid in $t1.Keys) {
  if ($t0.ContainsKey($tid)) {
    $pct = 100.0 * ($t1[$tid] - $t0[$tid]) / $wall
    if ($pct -ge 2.0) {
      $nm = [ThreadName]::Get($tid)
      if ([string]::IsNullOrEmpty($nm)) { $nm = "(unnamed)" }
      $rows += [pscustomobject]@{ Thread = $nm; Tid = $tid; Pct = [math]::Round($pct,1) }
    }
  }
}
$rows | Sort-Object Pct -Descending | Format-Table -AutoSize | Out-String | Write-Output
$tot = ($rows | Measure-Object -Property Pct -Sum).Sum
Write-Output ("total busy = {0}% of one core" -f [math]::Round($tot,1))

try { $null = $proc.CloseMainWindow() } catch {}
Start-Sleep -Seconds 4
if (Get-Process -Id $p.Id -ErrorAction SilentlyContinue) { Stop-Process -Id $p.Id -Force; Start-Sleep -Seconds 2 }
$out = "C:\Users\krisb\AppData\Local\Temp\claude\C--Users-krisb-code-high-fps-dolphin\9d264534-c37d-45b5-ba92-823468bd84b5\scratchpad"
foreach ($f in @("render_times.txt","vblank_times.txt")) {
  $src = Join-Path $logs $f
  if (Test-Path $src) { Copy-Item $src (Join-Path $out "$Label.$f") -Force }
}
Write-Output "stopped $Label"
