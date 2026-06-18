namespace ModbusModule
{
    public class PollingService(ModbusModule modbusModule)
    {
        #region Fields

        private ulong sequence;

        private CancellationTokenSource cancellationTokenSource;

        private ushort lastValue;

        private DateTime lastTimeGenerated = DateTime.Now;

        private object lockValues = new object();

        #endregion

        #region Public property

        public ushort LastValue
        {
            get
            {
                lock (lockValues)
                {
                    return lastValue;
                }
            }
        }

        public ulong Sequence
        {
            get
            {
                lock (lockValues)
                {
                    return sequence;
                }
            }
        }

        public DateTime GenerateLastTime
        {
            get
            {
                lock (lockValues)
                {
                    return lastTimeGenerated;
                }
            }
        }

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
                lock (lockValues)
                {
                    lastValue = modbusModule.Read();
                    sequence++;
                    lastTimeGenerated = DateTime.Now;
                }

                ValueChanged?.Invoke(sequence, lastValue, DateTime.Now);
                await Task.Delay(100, token);
            }
        }

        #endregion

        #region Events

        public event Action<ulong, ushort, DateTime> ValueChanged;

        #endregion
    }
}
