# Cria o atalho "Muvim" na área de trabalho, com o ícone do letreiro.
# O atalho roda abrir.pyw, que sobe o servidor se estiver parado e abre o site no navegador padrão.
$ErrorActionPreference = 'Stop'
$raiz = Split-Path -Parent $PSScriptRoot
$py = (Get-Command python -ErrorAction Stop).Source
$pyw = Join-Path (Split-Path $py) 'pythonw.exe'
if (-not (Test-Path $pyw)) { $pyw = $py }

$destino = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Muvim.lnk'
$sh = New-Object -ComObject WScript.Shell
$lnk = $sh.CreateShortcut($destino)
$lnk.TargetPath = $pyw
$lnk.Arguments = "`"$raiz\abrir.pyw`""
$lnk.WorkingDirectory = $raiz
$lnk.IconLocation = "$raiz\web\muvim.ico,0"
$lnk.Description = 'Muvim: lançamentos de filmes e séries'
$lnk.Save()
Write-Host "Atalho criado: $destino"
