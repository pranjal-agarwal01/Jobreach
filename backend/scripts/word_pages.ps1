# Count pages in Microsoft Word for every .docx listed in a manifest. Windows only.
# Word is the ground truth the LibreOffice + Carlito page check is tested against.
#
# Usage:  powershell -File scripts/word_pages.ps1 -Manifest out/parity/manifest.json -Out out/parity/word.json
# The manifest is a JSON array of objects with a "path" field (relative to the manifest).
param(
  [Parameter(Mandatory = $true)][string]$Manifest,
  [Parameter(Mandatory = $true)][string]$Out
)
$ErrorActionPreference = "Stop"
$base = Split-Path -Parent (Resolve-Path $Manifest)
$entries = Get-Content $Manifest -Raw | ConvertFrom-Json

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
$results = @{}
try {
  $i = 0
  foreach ($e in $entries) {
    $i++
    $full = Join-Path $base $e.path
    $doc = $word.Documents.Open($full, $false, $true)
    $results[$e.path] = $doc.ComputeStatistics(2)
    $doc.Close($false)
    if ($i % 25 -eq 0) { Write-Output ("  word: {0}/{1}" -f $i, $entries.Count) }
  }
} finally {
  $word.Quit()
  [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
}
# Write UTF-8 without a BOM so Python reads it with plain utf-8.
$outPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Out)
[System.IO.File]::WriteAllText($outPath, ($results | ConvertTo-Json -Depth 3))
Write-Output ("wrote {0} page counts to {1}" -f $results.Count, $Out)
