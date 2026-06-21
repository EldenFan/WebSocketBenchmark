using System.Collections.Concurrent;

namespace ModbusModule
{
    public class PollingService(ModbusModule modbusModule)
    {
        #region Fields
        private ulong sequence;
        private CancellationTokenSource cancellationTokenSource;
        private ushort lastValue;
        private DateTime lastTimeGenerated = DateTime.UtcNow;
        private readonly object lockValues = new();
        private readonly ConcurrentDictionary<ulong, (ushort Value, DateTime Timestamp)> history = new();
        #endregion

        #region Public properties
        public ushort LastValue { get { lock (lockValues) return lastValue; } }
        public ulong Sequence { get { lock (lockValues) return sequence; } }
        public DateTime GenerateLastTime { get { lock (lockValues) return lastTimeGenerated; } }
        #endregion

        #region Public methods

        public void Start()
        {
            cancellationTokenSource = new CancellationTokenSource();
            Task.Run(() => Execute(cancellationTokenSource.Token));
        }

        public void Stop() => cancellationTokenSource?.Cancel();

        public bool TryGetState(ulong seq, out ushort value, out DateTime timestamp)
        {
            if (history.TryGetValue(seq, out var state))
            {
                value = state.Value;
                timestamp = state.Timestamp;
                return true;
            }
            value = 0;
            timestamp = default;
            return false;
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
                    lastTimeGenerated = DateTime.UtcNow;
                    history[sequence] = (lastValue, lastTimeGenerated);
                }

                if (sequence > 200)
                {
                    history.TryRemove(sequence - 200, out _);
                }

                ValueChanged?.Invoke(sequence, lastValue, DateTime.UtcNow);

                await Task.Delay(100, token);
            }
        }
        #endregion

        public event Action<ulong, ushort, DateTime> ValueChanged;
    }
}