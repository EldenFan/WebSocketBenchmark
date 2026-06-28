#!/bin/bash

set -e

CONTAINER_NAME="websocketbenchmark"
METRICS_FILE="metrics.csv"

echo "Введите MODBUS_IP (по умолчанию: 192.168.31.250):"
read input_ip
export MODBUS_IP=${input_ip:-192.168.31.250}

echo "Введите MODBUS_PORT (по умолчанию: 500):"
read input_port
export MODBUS_PORT=${input_port:-500}

echo "Запускаем сервер..."
docker compose up -d --build

echo "Ждем начала..."
sleep 3

echo "Начинаем сбор метрик..."

echo "Time,CPU,Memory,MemPerc,PIDs" > "$METRICS_FILE"

(
  while true
  do
    TIMESTAMP=$(date +"%H:%M:%S")
    STATS=$(docker stats "$CONTAINER_NAME" --no-stream --format "{{.CPUPerc}},{{.MemUsage}},{{.MemPerc}},{{.PIDs}}")
    
    echo "$TIMESTAMP,$STATS" >> "$METRICS_FILE"
    sleep 1
  done
) &
METRICS_PID=$!

echo "Metrics PID: $METRICS_PID"
echo $METRICS_PID > metrics.pid

echo "Сервер запущен."
echo "Введите ENTER для окончания..."
read

kill $METRICS_PID
docker compose down