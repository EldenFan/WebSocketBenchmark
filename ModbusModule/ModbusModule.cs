using FluentModbus;
using System.Net;

namespace ModbusModule
{
    public class ModbusModule
    {
        private readonly ModbusTcpClient client;

        public ModbusModule()
        {
            client = new ModbusTcpClient();

            string modbusIp = Environment.GetEnvironmentVariable("MODBUS_IP") ?? "127.0.0.1";
            string modbusPort = Environment.GetEnvironmentVariable("MODBUS_PORT") ?? "500";

            client.Connect(IPEndPoint.Parse($"{modbusIp}:{modbusPort}"), ModbusEndianness.BigEndian);
        }

        public ushort Read()
        {
            var regs = client.ReadHoldingRegisters<ushort>(1, 1024, 1);

            return regs[0];
        }
    }
}
