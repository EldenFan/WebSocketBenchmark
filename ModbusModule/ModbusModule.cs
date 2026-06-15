using FluentModbus;

namespace ModbusModule
{
    public class ModbusModule
    {
        private readonly ModbusTcpClient client;

        public ModbusModule()
        {
            client = new ModbusTcpClient();

            client.Connect();
        }

        public ushort Read()
        {
            var regs = client.ReadHoldingRegisters(1, 0, 2);

            byte[] bytes = [(byte)(regs[0] >> 8), regs[0], (byte)(regs[1] >> 8), regs[1]];

            Array.Reverse(bytes);

            return BitConverter.ToUInt16(bytes, 0);
        }
    }
}
