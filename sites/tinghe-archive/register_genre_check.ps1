# Re-register tinghe-genre-check as the Administrator user, through the same
# wscript wrapper the other seven tasks use.
#
# Registration lives here rather than in Python because handing task XML to
# schtasks /Create from Python failed twice — once because the declaration said
# UTF-16 while the bytes were UTF-8, and again because schtasks /Query /XML emits
# UTF-16LE with no BOM, which does not survive subprocess. Both failures were
# reported as "contains an element or attribute from an unexpected namespace",
# which names the namespace rather than the encoding. The ScheduledTasks module
# reads and writes that export in its own native encoding, so neither problem
# exists here.
#
# Only the Principal and the Actions block are replaced; the namespace and
# everything else come from the system's own export, which round-trips.

$ErrorActionPreference = 'Stop'
$task = 'tinghe-genre-check'
$wrap = 'C:\tmp\tinghe-wrappers\tinghe-genre-check.cmd'

if (-not (Test-Path $wrap)) { throw "wrapper missing: $wrap" }

$doc = Export-ScheduledTask -TaskName $task
if (-not $doc) { throw "cannot export $task" }

$newPrincipal = @'
  <Principals>
    <Principal id="Author">
      <UserId>S-1-5-21-1422934702-2018621022-4115412978-500</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
'@

$newAction = @'
  <Actions Context="Author">
    <Exec>
      <Command>C:\Windows\System32\wscript.exe</Command>
      <Arguments>//B //nologo "C:\tmp\run-hidden-wait.vbs" "C:\tmp\tinghe-wrappers\tinghe-genre-check.cmd"</Arguments>
      <WorkingDirectory>C:\tmp\tinghe-wrappers</WorkingDirectory>
    </Exec>
  </Actions>
'@

$doc = [regex]::Replace($doc, '(?s)<Principals>.*?</Principals>', $newPrincipal.Trim())
$doc = [regex]::Replace($doc, '(?s)<Actions.*?</Actions>', $newAction.Trim())

Register-ScheduledTask -TaskName $task -Xml $doc -Force | Out-Null

$t = Get-ScheduledTask -TaskName $task
$i = Get-ScheduledTaskInfo -TaskName $task
Write-Output "re-registered $task"
Write-Output ("  user    : " + $t.Principal.UserId)
Write-Output ("  logon   : " + $t.Principal.LogonType)
Write-Output ("  command : " + $t.Actions[0].Execute)
Write-Output ("  next    : " + $i.NextRunTime)
if ($t.Principal.UserId -eq 'S-1-5-18') {
    throw "still registered as LOCAL SYSTEM — py -3 will not find Python"
}