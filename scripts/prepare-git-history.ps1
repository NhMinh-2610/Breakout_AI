param([ValidateSet('Plan','Commit')][string]$Mode = 'Plan')
$ErrorActionPreference = 'Stop'
$historyRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
function Invoke-HistoryGit {
    param([string[]]$GitArguments)
    $historyOutput = & git @GitArguments
    if ($LASTEXITCODE -ne 0) { throw "Git failed: $($GitArguments[0]). Inspect git status." }
    return $historyOutput
}
function Assert-HistoryPath {
    param([string]$RelativePath)
    if ($RelativePath -ne '.env.example' -and $RelativePath -match '(^|/)\.env($|\.)') { throw "Private file: $RelativePath" }
    if (($RelativePath -like 'data/*' -and $RelativePath -ne 'data/.gitkeep') -or
        $RelativePath -match '(^|/)(\.git|\.venv|\.artifacts|\.pytest_cache|__pycache__|\.tools)(/|$)' -or
        $RelativePath -match '\.(sqlite3?|db|pyc|log)(-|$|\.)') { throw "Private/generated file: $RelativePath" }
}
Push-Location -LiteralPath $historyRoot
try {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Install Git first.' }
    $historyGitRoot = [IO.Path]::GetFullPath((Invoke-HistoryGit -GitArguments @('rev-parse','--show-toplevel')))
    if ($historyGitRoot -ne $historyRoot) { throw 'Wrong repository root.' }
    $historyCount = Invoke-HistoryGit -GitArguments @('rev-list','--all','--count')
    if ([int]$historyCount -ne 0) { throw 'This helper only supports a repository without commits. It never rewrites history.' }
    if (@(Invoke-HistoryGit -GitArguments @('diff','--cached','--name-only')).Count -ne 0) { throw 'Index already contains staged changes; review first.' }
    $historyPlan = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'git-history-plan.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($historyPlan.kind -ne 'reconstructed-history') { throw 'Unexpected plan type.' }
    $historySeen = @{}
    $historyResolved = @()
    $historyPrevious = [datetimeoffset]::MinValue
    foreach ($historyItem in $historyPlan.commits) {
        $historyDate = [datetimeoffset]::Parse($historyItem.date, [Globalization.CultureInfo]::InvariantCulture)
        if ($historyDate -le $historyPrevious -or $historyDate -gt [datetimeoffset]::UtcNow) { throw 'Dates must increase and cannot be in the future.' }
        $historyPrevious = $historyDate
        if ($historyItem.subject -notmatch '^[\x20-\x7E]+$' -or $historyItem.subject.Length -gt 72) { throw 'Use a short English subject.' }
        $historyFiles = @()
        foreach ($historyEntry in $historyItem.paths) {
            $historyFull = [IO.Path]::GetFullPath((Join-Path $historyRoot $historyEntry))
            if (-not $historyFull.StartsWith($historyRoot + [IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) { throw 'Path escapes project.' }
            if (-not (Test-Path -LiteralPath $historyFull)) { throw "Missing path: $historyEntry" }
            $historyItems = if (Test-Path -LiteralPath $historyFull -PathType Container) { @(Get-ChildItem -LiteralPath $historyFull -Recurse -File) } else { @(Get-Item -LiteralPath $historyFull) }
            foreach ($historyFile in $historyItems) {
                if (($historyFile.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Review symlinks manually.' }
                $historyRelative = $historyFile.FullName.Substring($historyRoot.Length + 1).Replace('\','/')
                Assert-HistoryPath -RelativePath $historyRelative
                if ($historySeen.ContainsKey($historyRelative)) { throw "Duplicate path: $historyRelative" }
                $historySeen[$historyRelative] = $true
                $historyFiles += $historyRelative
            }
        }
        $historyResolved += [pscustomobject]@{date=$historyItem.date;subject=$historyItem.subject;body=$historyItem.body;files=$historyFiles}
    }
    $historyUntracked = @(Invoke-HistoryGit -GitArguments @('-c','core.quotepath=false','ls-files','--others','--exclude-standard'))
    foreach ($historyFile in $historyUntracked) { if (-not $historySeen.ContainsKey($historyFile)) { throw "Unplanned file: $historyFile" } }
    foreach ($historyFile in $historySeen.Keys) { if ($historyFile -notin $historyUntracked) { throw "Ignored or unavailable file: $historyFile" } }
    Write-Output 'RECONSTRUCTED HISTORY - proposed milestones, not verified work dates.'
    foreach ($historyItem in $historyResolved) {
        Write-Output ("{0}  {1} ({2} files)" -f $historyItem.date,$historyItem.subject,$historyItem.files.Count)
        Write-Output ("    {0}" -f $historyItem.body)
    }
    if ($Mode -eq 'Plan') { Write-Output 'Preview only: nothing staged, committed or pushed.'; return }
    $null = Invoke-HistoryGit -GitArguments @('config','--get','user.name')
    $null = Invoke-HistoryGit -GitArguments @('config','--get','user.email')
    $historyOldAuthor = [Environment]::GetEnvironmentVariable('GIT_AUTHOR_DATE','Process')
    $historyOldCommitter = [Environment]::GetEnvironmentVariable('GIT_COMMITTER_DATE','Process')
    $historyMessagePath = Join-Path $historyRoot ('.artifacts\git-message-' + [guid]::NewGuid().ToString('N') + '.txt')
    $null = New-Item -ItemType Directory -Path (Split-Path -Parent $historyMessagePath) -Force
    $historyLF = [string][char]10
    try {
        foreach ($historyItem in $historyResolved) {
            [Environment]::SetEnvironmentVariable('GIT_AUTHOR_DATE',$historyItem.date,'Process')
            [Environment]::SetEnvironmentVariable('GIT_COMMITTER_DATE',$historyItem.date,'Process')
            [IO.File]::WriteAllText($historyMessagePath,$historyItem.subject+$historyLF+$historyLF+$historyItem.body+$historyLF,[Text.UTF8Encoding]::new($false))
            $null = Invoke-HistoryGit -GitArguments (@('add','--') + $historyItem.files)
            Invoke-HistoryGit -GitArguments @('commit','--file',$historyMessagePath)
        }
    } finally {
        [Environment]::SetEnvironmentVariable('GIT_AUTHOR_DATE',$historyOldAuthor,'Process')
        [Environment]::SetEnvironmentVariable('GIT_COMMITTER_DATE',$historyOldCommitter,'Process')
        if (Test-Path -LiteralPath $historyMessagePath) { Remove-Item -LiteralPath $historyMessagePath }
    }
    Invoke-HistoryGit -GitArguments @('log','--reverse','--format=%h %aI | %cI | %s')
    Write-Output 'Local history created. This script never pushes or configures a remote.'
} finally { Pop-Location }
