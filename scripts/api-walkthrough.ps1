param([string]$BaseUrl = 'http://127.0.0.1:5190')
$ErrorActionPreference = 'Stop'
$labUri = [Uri]$BaseUrl
if ($labUri.Scheme -ne 'http' -or $labUri.Host -notin @('localhost','127.0.0.1')) {
    throw 'Use the local loopback lab only.'
}
$page = (Invoke-WebRequest $BaseUrl).Content
$tokenMatch = [regex]::Match($page, 'name="lab-token" content="([^"]+)"')
if (-not $tokenMatch.Success) { throw 'Local dashboard token not found.' }
$headers = @{ 'X-Lab-Token' = $tokenMatch.Groups[1].Value }
$job = Invoke-RestMethod "$BaseUrl/api/jobs" -Method Post -ContentType 'application/json' -Headers $headers -Body '{"seconds":5}'
$deadline = [DateTime]::UtcNow.AddSeconds(40)
do {
    Start-Sleep -Seconds 1
    $job = Invoke-RestMethod "$BaseUrl/api/jobs/$($job.id)"
    if ([DateTime]::UtcNow -gt $deadline) { throw 'Workflow did not complete within the walkthrough deadline.' }
} while ($job.status -in @('starting','running','stopping'))
Remove-Variable headers,page,tokenMatch
$job | ConvertTo-Json -Depth 8
if ($job.status -ne 'completed') { throw "Workflow ended with status $($job.status)" }
