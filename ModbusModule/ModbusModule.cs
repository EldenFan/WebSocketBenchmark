using FluentModbus;

namespace ModbusModule
{
    public class ModbusModule
    {
        private readonly ModbusTcpClient client;

        public ModbusModule()
        {
            client = new ModbusTcpClient();

            client.Connect(ModbusEndianness.BigEndian);
        }

        public ushort Read()
        {
            var regs = client.ReadHoldingRegisters<ushort>(1, 1024, 1);

            return regs[0];
        }
    }
}
