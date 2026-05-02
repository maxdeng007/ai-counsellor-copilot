// AudioWorkletProcessor runs on the audio render thread.
// It forwards mono Float32 PCM frames to the main thread for conversion + WS send.

class PcmWorkletProcessor extends AudioWorkletProcessor {
  process(inputs, outputs) {
    const input = inputs?.[0]
    const channel0 = input?.[0]
    if (channel0 && channel0.length) {
      const output = outputs?.[0]
      const out0 = output?.[0]
      if (out0) out0.set(channel0)
      // Copy to avoid transferring a view backed by a recycled buffer.
      this.port.postMessage(channel0.slice(0))
    }
    return true
  }
}

registerProcessor('pcm-worklet', PcmWorkletProcessor)

