@echo off

cd F:\WebSocketBenchmark\TestLauncher\bin\Release\net8.0\Captures

for %%f in (*.pcap) do (
    for /f "tokens=*" %%i in ('tshark -r "%%f" -c 1 -T fields -e frame.time') do (
        echo %%f: %%i
    )
)

pause