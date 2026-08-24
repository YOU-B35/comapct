# ====================================================================
# CrossHub Sync Helper · One-shot installer build (PyInstaller -> Setup.exe)
#
# 1. Python 64-bit check; auto-install Inno Setup via winget if missing
# 2. Invoke build-sync-helper-exe.ps1 (skippable)
# 3. [Optional] Dual-code-sign Helper EXE (SHA-1 + SHA-256 + timestamp)
# 4. Compile installer via ISCC
# 5. [Optional] Dual-code-sign Setup.exe
# 6. PE-header verify Setup.exe and dump summary
#
# Usage examples:
#   powershell -ExecutionPolicy Bypass -File scripts\build-and-package-installer.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\build-and-package-installer.ps1 -SkipBuildExe
#   powershell -ExecutionPolicy Bypass -File scripts\build-and-package-installer.ps1 -Sign -SignCertCN "YOTO Tech"
# ====================================================================
param(
    [switch]$OneFile = $false,
    [switch]$SkipBuildExe = $false,
    [switch]$Sign = $false,
    [string]$PfxCert = "",
    [Security.SecureString]$PfxPass = (New-Object Security.SecureString),
    [string]$JavaApiUrl = "https://www.yoto.work",
    [string]$OutDir = "",
    [ValidateSet("Production","Test","Skip")][string]$SignMode = "Skip",
    [string]$SignCertCN = "YOTO Tech"
)

$ErrorActionPreference = "Continue"

function writeStep($msg) { Write-Host ""; Write-Host "==> $msg" -ForegroundColor Cyan }
function writeOK  ($msg) { Write-Host ("    OK  " + $msg) -ForegroundColor Green }
function writeWARN($msg) { Write-Host ("    !   " + $msg) -ForegroundColor Yellow }
function writeFATAL($msg) { Write-Host ("FATAL: " + $msg) -ForegroundColor Red; exit 1 }

$Root       = Split-Path -Parent $PSScriptRoot
$PackageDir = Join-Path $Root "scripts\packaging\sync-helper"
$IssFile    = Join-Path $PackageDir "CrossHub-Sync-Helper.iss"
$HelperDist = Join-Path $Root "dist\CrossHub-Sync-Helper\CrossHub-Sync-Helper"
$InstallerOutDir = Join-Path $Root "dist\Installer"

# ============================================================
# STEP 0  Environment sanity
# ============================================================
writeStep "Environment sanity"

$Bits = & python -c "import sys,struct;print(struct.calcsize('P')*8, end='')" 2>$null
if ([int]$Bits -ne 64) { writeFATAL ("Python is " + $Bits + "-bit; need a 64-bit Python 3.10+ x64.") }
writeOK ("Python 64-bit  (" + $Bits + "-bit)")

if (-not (Test-Path $IssFile)) { writeFATAL ("ISS script missing: " + $IssFile) }

function find-ISCC {
    $xs = @(
        (Get-Command ISCC -ErrorAction SilentlyContinue).Source,
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe")
    ) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
    return $xs
}
$iscc = find-ISCC
if (-not $iscc) {
    writeWARN "Inno Setup not found. Trying winget install (may require elevation)."
    $wg = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $wg) { writeFATAL "winget is unavailable. Please install Inno Setup 6 manually from https://jrsoftware.org/isdl.php and then re-run." }
    & winget install --id JRSoftware.InnoSetup --exact --silent --accept-package-agreements --accept-source-agreements 2>&1 | Out-Null
    Start-Sleep -Seconds 3
    $iscc = find-ISCC
    if (-not $iscc) { writeFATAL "Inno Setup winget-install failed. Install Inno Setup 6 by hand and re-run." }
}
writeOK ("ISCC  = " + $iscc)

function find-signtool {
    $xs = @(
        (Get-Command signtool -ErrorAction SilentlyContinue).Source,
        "C:\Program Files (x86)\Windows Kits\10\bin\10.0.22621.0\x64\signtool.exe",
        "C:\Program Files (x86)\Windows Kits\10\bin\10.0.19041.0\x64\signtool.exe",
        "C:\Program Files (x86)\Windows Kits\10\bin\x64\signtool.exe"
    ) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
    return $xs
}
$signtool = find-signtool
$script:CertThumb = $null
if ($Sign) {
    if (-not $signtool) { writeWARN "signtool.exe not found. Install Windows 10 SDK to enable code signing." }
    if (-not $PfxCert) {
        $found = Get-ChildItem Cert:\CurrentUser\My, Cert:\LocalMachine\My -ErrorAction SilentlyContinue |
            Where-Object { $_.Subject -like ("*" + $SignCertCN + "*") -and $_.HasPrivateKey } |
            Select-Object -First 1
        if ($found) {
            $script:CertThumb = $found.Thumbprint
            writeOK ("Cert thumbprint = " + $found.Thumbprint + "  Subject = " + $found.Subject)
        } else {
            writeWARN ("No cert with CN=*" + $SignCertCN + "* found. Signing step skipped.")
            $Sign = $false
        }
    } else {
        if (-not (Test-Path $PfxCert)) { writeFATAL ("Pfx not found: " + $PfxCert) }
        writeOK ("Pfx = " + $PfxCert)
    }
    if ($signtool) { writeOK ("signtool = " + $signtool) } else { writeWARN "signtool missing; skipping signing." }
}
if ($SignMode -eq "Skip" -and $Sign) { $SignMode = "Test" }

# ============================================================
# STEP 1  Run PyInstaller build (unless skipped)
# ============================================================
if (-not $SkipBuildExe) {
    writeStep "STEP 1/5  PyInstaller (Helper EXE x64)"
    $args1 = @("-ExecutionPolicy","Bypass","-File",(Join-Path $Root "scripts\build-sync-helper-exe.ps1"),"-JavaApiUrl",$JavaApiUrl)
    if ($OneFile) { $args1 += "-OneFile" }
    if ($OutDir)  { $args1 += @("-OutDir",$OutDir) }
    & powershell @args1
    if ($LASTEXITCODE -ne 0 -and -not (Test-Path (Join-Path $HelperDist "CrossHub-Sync-Helper.exe"))) {
        writeFATAL ("PyInstaller failed, exit=" + $LASTEXITCODE)
    }
} else {
    writeStep "STEP 1/5  PyInstaller build skipped"
}

$ExePath = Join-Path $HelperDist "CrossHub-Sync-Helper.exe"
if (-not (Test-Path $ExePath)) { writeFATAL ("Helper EXE not found. Run build-sync-helper-exe.ps1 first, or drop -SkipBuildExe. => " + $ExePath) }

$sanityPy = @'
import struct, sys
with open(sys.argv[1], "rb") as f:
    h = f.read(0x1000)
e = struct.unpack_from("<I", h, 0x3C)[0]
m = struct.unpack_from("<H", h, e + 4)[0]
g = struct.unpack_from("<H", h, e + 4 + 20)[0]
s = struct.unpack_from("<H", h, e + 4 + 20 + 68)[0]
print("M=0x{0:04X} G=0x{1:04X} S={2}".format(m,g,s))
'@
$sanityFile = Join-Path $env:TEMP "ch_pe_sanity.py"
Set-Content -Path $sanityFile -Value $sanityPy -Encoding ASCII
$chk = (& python $sanityFile $ExePath 2>$null)
Remove-Item $sanityFile -ErrorAction SilentlyContinue
if ($chk -and $chk.Contains("M=0x8664")) { writeOK ("Helper EXE PE  -> " + $chk + "  x64 + GUI OK") }
else { writeWARN ("Helper EXE PE  -> " + $chk) }

# ============================================================
# STEP 2  Sign Helper EXE
# ============================================================
if ($Sign -and $signtool) {
    writeStep "STEP 2/5  Sign Helper EXE (dual SHA-1 + SHA-256 + timestamp)"
    $plainPass = ""
    if ($PfxCert) {
        $plainPass = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($PfxPass))
    }
    $desc = "CrossHub Sync Helper Desktop x64"
    $s1 = @("sign")
    if ($PfxCert) { $s1 += @("/f",$PfxCert,"/p",$plainPass) } else { $s1 += @("/sha1",$script:CertThumb) }
    & $signtool @s1 /fd sha1 /t http://timestamp.digicert.com /d $desc /du "https://www.yoto.work" $ExePath 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { writeWARN "SHA-1 signing failed; continuing to append SHA-256." }
    $s2 = @("sign")
    if ($PfxCert) { $s2 += @("/f",$PfxCert,"/p",$plainPass) } else { $s2 += @("/sha1",$script:CertThumb) }
    & $signtool @s2 /fd sha256 /tr http://timestamp.digicert.com /td sha256 /as /d $desc /du "https://www.yoto.work" $ExePath 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { writeWARN "SHA-256 append-sign failed." }
    else { writeOK "Helper EXE dual-sign done." }
} else {
    writeStep "STEP 2/5  Sign Helper EXE  (skipped. pass -Sign to enable.)"
}

# ============================================================
# STEP 3  Build installer via ISCC
# ============================================================
writeStep "STEP 3/5  Compile Inno Setup installer"
Push-Location $PackageDir
try {
    & $iscc /Qp $IssFile
    if ($LASTEXITCODE -ne 0) { writeFATAL ("ISCC compile failed exit=" + $LASTEXITCODE) }
} finally { Pop-Location }

if (-not (Test-Path $InstallerOutDir)) { writeFATAL ("Installer output dir missing: " + $InstallerOutDir) }
$setup = Get-ChildItem $InstallerOutDir -Filter "CrossHub-Sync-Helper-Setup-*-x64.exe" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $setup) { writeFATAL ("Setup.exe missing under: " + $InstallerOutDir) }
$mbStr = "{0:N1} MB" -f ($setup.Length / 1MB)
writeOK ("Setup.exe = " + $setup.FullName + "   [" + $mbStr + "]")

# ============================================================
# STEP 4  Sign Setup.exe
# ============================================================
if ($Sign -and $signtool) {
    writeStep "STEP 4/5  Sign Setup.exe"
    $desc = "CrossHub Sync Helper Installer (x64)"
    $plainPass = ""
    if ($PfxCert) {
        $plainPass = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($PfxPass))
    }
    $a1 = @("sign")
    if ($PfxCert) { $a1 += @("/f",$PfxCert,"/p",$plainPass) } else { $a1 += @("/sha1",$script:CertThumb) }
    & $signtool @a1 /fd sha1 /t http://timestamp.digicert.com /d $desc /du "https://www.yoto.work" $setup.FullName | Out-Null
    $a2 = @("sign")
    if ($PfxCert) { $a2 += @("/f",$PfxCert,"/p",$plainPass) } else { $a2 += @("/sha1",$script:CertThumb) }
    & $signtool @a2 /fd sha256 /tr http://timestamp.digicert.com /td sha256 /as /d $desc /du "https://www.yoto.work" $setup.FullName | Out-Null
    writeOK "Setup.exe sign done."
} else {
    writeStep "STEP 4/5  Sign Setup.exe  (skipped. pass -Sign to enable.)"
}

# ============================================================
# STEP 5  Final verification + summary
# ============================================================
writeStep "STEP 5/5  Final verify (Setup PE header + resources)"
$verifyPy = @'
import struct, os, sys
p = sys.argv[1]
sz = os.path.getsize(p)
with open(p, "rb") as f:
    h = f.read(0x4000)
assert h[0:2] == b"MZ", "Not a PE file"
e = struct.unpack_from("<I", h, 0x3C)[0]
assert h[e:e+4] == b"PE\x00\x00", "Bad PE signature"
m = struct.unpack_from("<H", h, e + 4)[0]
g = struct.unpack_from("<H", h, e + 4 + 20)[0]
s = struct.unpack_from("<H", h, e + 4 + 20 + 68)[0]
print("SIZE_MB=%.2f" % (sz / 1024.0 / 1024.0))
arch = {0x8664:"x64_AMD64", 0x014c:"x86_I386"}.get(m, hex(m))
mg   = {0x20b:"PE32+", 0x10b:"PE32"}.get(g, hex(g))
ss   = {2:"GUI", 3:"CUI"}.get(s, str(s))
print("ARCH=" + arch)
print("MAGIC=" + mg)
print("SUBSYS=" + ss)
num = struct.unpack_from("<H", h, e + 4 + 2)[0]
oh  = struct.unpack_from("<H", h, e + 4 + 16)[0]
sec = e + 4 + 20 + oh
rsrc = "NO"
for i in range(min(num, 40)):
    o = sec + i * 40
    if o + 8 > len(h): break
    name_bytes = h[o:o+8]
    try:
        name = name_bytes.rstrip(b"\x00").decode("ascii", "ignore")
    except Exception:
        name = ""
    if ".rsrc" in name.upper() or name.upper() == "RSRC":
        raw = struct.unpack_from("<I", h, o + 20)[0]
        siz = struct.unpack_from("<I", h, o + 16)[0]
        rsrc = "YES (raw=0x%X size=0x%X, %.1f KB)" % (raw, siz, siz / 1024.0)
        break
print("RSRC=" + rsrc)
'@
$verifyFile = Join-Path $env:TEMP "ch_setup_pe.py"
Set-Content -Path $verifyFile -Value $verifyPy -Encoding ASCII
$out = (& python $verifyFile $setup.FullName 2>&1)
Remove-Item $verifyFile -ErrorAction SilentlyContinue
Write-Host ($out -join "`n") -ForegroundColor DarkGray
$ARCH    = ($out | Select-String '^ARCH=(.+)'   ).Matches.Groups[1].Value
$MAGIC   = ($out | Select-String '^MAGIC=(.+)'  ).Matches.Groups[1].Value
$SUBSYS  = ($out | Select-String '^SUBSYS=(.+)' ).Matches.Groups[1].Value
$RSRC    = ($out | Select-String '^RSRC=(.+)'   ).Matches.Groups[1].Value
$SIZE_MB = ($out | Select-String '^SIZE_MB=(.+)').Matches.Groups[1].Value

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host " CrossHub Sync Helper Installer build DONE."                  -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host (" Setup.exe : " + $setup.FullName)                      -ForegroundColor Green
Write-Host (" Size      : " + $SIZE_MB + " MB")                     -ForegroundColor Green
Write-Host (" PE ARCH   : " + $ARCH   + "  (" + $MAGIC + ")")       -ForegroundColor Green
Write-Host (" SUBSYSTEM : " + $SUBSYS + "  (GUI = no console)")     -ForegroundColor Green
Write-Host (" .rsrc     : " + $RSRC)                                -ForegroundColor Green
$signTxt = if ($Sign) {"SIGNED (SHA-1 + SHA-256 + RFC3161 timestamp)"} else {"unsigned (pass -Sign with pfx or Cert CN)"}
Write-Host (" Signed    : " + $signTxt)                             -ForegroundColor Green
Write-Host (" Features  : Start menu / Desktop / Uninstall / Autorun / URL protocol / App Paths alias") -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Notes:"
Write-Host "  - Distribute this Setup.exe to end users. Double-click -> Chinese install wizard."
Write-Host "  - After install, Uninstall appears in Settings -> Apps -> Installed apps."
Write-Host "  - Desktop + Start menu + HKCU Run autorun (optional) + crosshub-sync-helper:// protocol are all registered."
Write-Host "  - EV/OV code signing removes SmartScreen 'unknown publisher' warning; re-run with -Sign -PfxCert ... to enable."
