FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src

COPY ["WebSocketBenchmark/WebSocketBenchmark.csproj", "WebSocketBenchmark/"]
COPY ["ModbusModule/ModbusModule.csproj", "ModbusModule/"]

RUN dotnet restore "WebSocketBenchmark/WebSocketBenchmark.csproj"

COPY . .

RUN dotnet publish "WebSocketBenchmark/WebSocketBenchmark.csproj" -c Release -o /app/publish

FROM mcr.microsoft.com/dotnet/aspnet:8.0
WORKDIR /app
COPY --from=build /app/publish .

EXPOSE 5000

ENTRYPOINT ["dotnet", "WebSocketBenchmark.dll"]