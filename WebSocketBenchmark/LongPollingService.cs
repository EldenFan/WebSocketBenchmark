using System.Collections.Concurrent;

namespace WebSocketBenchmark
{
    public class LongPollingService
    {
        private readonly ConcurrentDictionary<Guid, TaskCompletionSource<(ulong Sequence, ushort Value, DateTime Timestamp)>> waiters = new();

        public Task<(ulong Sequence, ushort Value, DateTime Timestamp)> WaitForUpdateAsync(
            CancellationToken token)
        {
            var id = Guid.NewGuid();

            var tcs = new TaskCompletionSource<(ulong, ushort, DateTime)>(TaskCreationOptions.RunContinuationsAsynchronously);

            waiters.TryAdd(id, tcs);

            token.Register(() =>
            {
                waiters.TryRemove(id, out _);
                tcs.TrySetCanceled();
            });

            return tcs.Task;
        }

        public void Notify(ulong sequence, ushort value, DateTime timeStamp)
        {
            Task.Run(() =>
            {
                foreach (var pair in waiters)
                {
                    if (waiters.TryRemove(pair.Key, out var tcs))
                    {
                        tcs.TrySetResult((sequence, value, timeStamp));
                    }
                }
            }
            );
        }
    }
}
