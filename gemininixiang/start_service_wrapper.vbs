Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' 获取脚本所在目录
scriptPath = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = scriptPath

' 启动 Python 服务（隐藏窗口，输出重定向到日志文件）
logFile = scriptPath & "\service.log"
pythonCmd = "python server.py > """ & logFile & """ 2>&1"

' 使用 Run 方法启动，参数说明：
' 0 = 隐藏窗口
' False = 不等待进程结束
WshShell.Run "cmd /c """ & pythonCmd & """", 0, False

Set WshShell = Nothing
Set fso = Nothing


