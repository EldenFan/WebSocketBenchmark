FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src

COPY ["WebServer/WebServer.csproj", "WebServer/"]
COPY ["ModbusModule/ModbusModule.csproj", "ModbusModule/"]

RUN dotnet restore "WebServer/WebServer.csproj"

COPY . .

RUN dotnet publish "WebServer/WebServer.csproj" -c Release -o /app/publish

FROM mcr.microsoft.com/dotnet/runtime:8.0
WORKDIR /app
COPY --from=build /app/publish .

EXPOSE 5000

ENTRYPOINT ["dotnet", "WebServer.dll"]