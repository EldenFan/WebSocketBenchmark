namespace ModbusModule
{
    public class PollingService(ModbusModule modbusModule)
    {
        #region Fields

        private ulong sequency;

        private CancellationTokenSource cancellationTokenSource;

        #endregion

        #region Public methods

        public void Start()
        {
            cancellationTokenSource = new CancellationTokenSource();
            Task.Run(() => Execute(cancellationTokenSource.Token));
        }

        public void Stop()
        {
            cancellationTokenSource?.Cancel();
        }

        #endregion

        #region Private methods

        private async Task Execute(CancellationToken token)
        {
            while (!token.IsCancellationRequested)
            {
                var value = modbusModule.Read();
                sequency++;
                ValueRecieved?.Invoke(sequency, value);
                await Task.Delay(100, token);
            }
        }

        #endregion

        #region Events

        public event Action<ulong, ushort> ValueRecieved;

        #endregion
    }
}
