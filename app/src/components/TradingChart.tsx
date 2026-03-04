"use client";

import { useEffect, useRef, useState } from "react";
import type { Candle } from "@/lib/hooks/useMarketData";
import { sma, ema, bollingerBands, rsi, macd } from "@/lib/indicators";
import type { OHLCData } from "@/lib/indicators";

type TabKey = "price" | "volume" | "indicators";

const TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1d"] as const;
const TIMEFRAME_LIMITS: Record<string, number> = {
  "1m": 120,
  "5m": 120,
  "15m": 96,
  "1h": 168,
  "4h": 120,
  "1d": 90,
};

interface TradingChartProps {
  symbol: string;
  candles: Candle[] | undefined;
  isLoading: boolean;
  onTimeframeChange: (tf: string, limit: number) => void;
}

export function TradingChart({ symbol, candles, isLoading, onTimeframeChange }: TradingChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const volumeContainerRef = useRef<HTMLDivElement>(null);
  const indicatorContainerRef = useRef<HTMLDivElement>(null);
  const [activeTab, setActiveTab] = useState<TabKey>("price");
  const [timeframe, setTimeframe] = useState("1h");
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const chartRef = useRef<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const volumeChartRef = useRef<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const indicatorChartRef = useRef<any>(null);

  const handleTfChange = (tf: string) => {
    setTimeframe(tf);
    onTimeframeChange(tf, TIMEFRAME_LIMITS[tf] || 100);
  };

  // Convert candles to OHLC format for indicators
  const ohlcData: OHLCData[] = (candles ?? []).map((c) => ({
    time: Math.floor(c.timestamp / 1000),
    open: c.open,
    high: c.high,
    low: c.low,
    close: c.close,
    volume: c.volume,
  }));

  // Price chart with candlesticks + overlays
  useEffect(() => {
    if (activeTab !== "price" || !chartContainerRef.current || ohlcData.length < 2) return;

    let chart: ReturnType<typeof import("lightweight-charts").createChart> | null = null;

    const setupChart = async () => {
      const { createChart, CandlestickSeries, LineSeries } = await import("lightweight-charts");

      if (!chartContainerRef.current) return;

      // Clear previous
      chartContainerRef.current.innerHTML = "";

      chart = createChart(chartContainerRef.current, {
        width: chartContainerRef.current.clientWidth,
        height: 380,
        layout: { background: { color: "transparent" }, textColor: "#6b7280", fontSize: 11 },
        grid: {
          vertLines: { color: "rgba(255,255,255,0.03)" },
          horzLines: { color: "rgba(255,255,255,0.03)" },
        },
        crosshair: { mode: 0 },
        rightPriceScale: { borderColor: "rgba(255,255,255,0.1)" },
        timeScale: { borderColor: "rgba(255,255,255,0.1)", timeVisible: true },
      });

      // Candlestick series
      const candleSeries = chart.addSeries(CandlestickSeries, {
        upColor: "#10b981",
        downColor: "#ef4444",
        borderUpColor: "#10b981",
        borderDownColor: "#ef4444",
        wickUpColor: "#10b981",
        wickDownColor: "#ef4444",
      });
      candleSeries.setData(
        ohlcData.map((d) => ({
          time: d.time as import("lightweight-charts").UTCTimestamp,
          open: d.open,
          high: d.high,
          low: d.low,
          close: d.close,
        }))
      );

      // SMA 20
      const sma20 = sma(ohlcData, 20);
      if (sma20.length > 0) {
        const sma20Series = chart.addSeries(LineSeries, {
          color: "#f59e0b",
          lineWidth: 1,
          priceLineVisible: false,
          lastValueVisible: false,
        });
        sma20Series.setData(sma20.map((p) => ({ time: p.time as import("lightweight-charts").UTCTimestamp, value: p.value })));
      }

      // SMA 50
      const sma50 = sma(ohlcData, 50);
      if (sma50.length > 0) {
        const sma50Series = chart.addSeries(LineSeries, {
          color: "#8b5cf6",
          lineWidth: 1,
          priceLineVisible: false,
          lastValueVisible: false,
        });
        sma50Series.setData(sma50.map((p) => ({ time: p.time as import("lightweight-charts").UTCTimestamp, value: p.value })));
      }

      // EMA 12
      const ema12 = ema(ohlcData, 12);
      if (ema12.length > 0) {
        const ema12Series = chart.addSeries(LineSeries, {
          color: "#06b6d4",
          lineWidth: 1,
          priceLineVisible: false,
          lastValueVisible: false,
        });
        ema12Series.setData(ema12.map((p) => ({ time: p.time as import("lightweight-charts").UTCTimestamp, value: p.value })));
      }

      // Bollinger Bands
      const bb = bollingerBands(ohlcData, 20, 2);
      if (bb.upper.length > 0) {
        const bbUpper = chart.addSeries(LineSeries, {
          color: "rgba(139, 92, 246, 0.3)",
          lineWidth: 1,
          priceLineVisible: false,
          lastValueVisible: false,
        });
        bbUpper.setData(bb.upper.map((p) => ({ time: p.time as import("lightweight-charts").UTCTimestamp, value: p.value })));

        const bbLower = chart.addSeries(LineSeries, {
          color: "rgba(139, 92, 246, 0.3)",
          lineWidth: 1,
          priceLineVisible: false,
          lastValueVisible: false,
        });
        bbLower.setData(bb.lower.map((p) => ({ time: p.time as import("lightweight-charts").UTCTimestamp, value: p.value })));
      }

      chart.timeScale().fitContent();
      chartRef.current = chart;
    };

    setupChart();

    const resizeObserver = new ResizeObserver(() => {
      if (chartRef.current && chartContainerRef.current) {
        chartRef.current.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
    });
    resizeObserver.observe(chartContainerRef.current);

    return () => {
      resizeObserver.disconnect();
      if (chart) chart.remove();
      chartRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, candles]);

  // Volume chart
  useEffect(() => {
    if (activeTab !== "volume" || !volumeContainerRef.current || ohlcData.length < 2) return;

    let chart: ReturnType<typeof import("lightweight-charts").createChart> | null = null;

    const setupChart = async () => {
      const { createChart, HistogramSeries } = await import("lightweight-charts");

      if (!volumeContainerRef.current) return;
      volumeContainerRef.current.innerHTML = "";

      chart = createChart(volumeContainerRef.current, {
        width: volumeContainerRef.current.clientWidth,
        height: 380,
        layout: { background: { color: "transparent" }, textColor: "#6b7280", fontSize: 11 },
        grid: {
          vertLines: { color: "rgba(255,255,255,0.03)" },
          horzLines: { color: "rgba(255,255,255,0.03)" },
        },
        rightPriceScale: { borderColor: "rgba(255,255,255,0.1)" },
        timeScale: { borderColor: "rgba(255,255,255,0.1)", timeVisible: true },
      });

      const volumeSeries = chart.addSeries(HistogramSeries, {
        priceLineVisible: false,
        lastValueVisible: false,
      });
      volumeSeries.setData(
        ohlcData.map((d) => ({
          time: d.time as import("lightweight-charts").UTCTimestamp,
          value: d.volume,
          color: d.close >= d.open ? "rgba(16, 185, 129, 0.5)" : "rgba(239, 68, 68, 0.5)",
        }))
      );

      chart.timeScale().fitContent();
      volumeChartRef.current = chart;
    };

    setupChart();

    const resizeObserver = new ResizeObserver(() => {
      if (volumeChartRef.current && volumeContainerRef.current) {
        volumeChartRef.current.applyOptions({ width: volumeContainerRef.current.clientWidth });
      }
    });
    resizeObserver.observe(volumeContainerRef.current);

    return () => {
      resizeObserver.disconnect();
      if (chart) chart.remove();
      volumeChartRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, candles]);

  // Indicators chart (RSI + MACD)
  useEffect(() => {
    if (activeTab !== "indicators" || !indicatorContainerRef.current || ohlcData.length < 30) return;

    let chart: ReturnType<typeof import("lightweight-charts").createChart> | null = null;

    const setupChart = async () => {
      const { createChart, LineSeries, HistogramSeries } = await import("lightweight-charts");

      if (!indicatorContainerRef.current) return;
      indicatorContainerRef.current.innerHTML = "";

      chart = createChart(indicatorContainerRef.current, {
        width: indicatorContainerRef.current.clientWidth,
        height: 380,
        layout: { background: { color: "transparent" }, textColor: "#6b7280", fontSize: 11 },
        grid: {
          vertLines: { color: "rgba(255,255,255,0.03)" },
          horzLines: { color: "rgba(255,255,255,0.03)" },
        },
        rightPriceScale: { borderColor: "rgba(255,255,255,0.1)" },
        timeScale: { borderColor: "rgba(255,255,255,0.1)", timeVisible: true },
      });

      // RSI
      const rsiData = rsi(ohlcData, 14);
      if (rsiData.length > 0) {
        const rsiSeries = chart.addSeries(LineSeries, {
          color: "#f59e0b",
          lineWidth: 2,
          priceLineVisible: false,
          lastValueVisible: true,
        });
        rsiSeries.setData(rsiData.map((p) => ({ time: p.time as import("lightweight-charts").UTCTimestamp, value: p.value })));
      }

      // MACD histogram
      const macdData = macd(ohlcData);
      if (macdData.histogram.length > 0) {
        const histSeries = chart.addSeries(HistogramSeries, {
          priceLineVisible: false,
          lastValueVisible: false,
          priceScaleId: "macd",
        });
        histSeries.setData(
          macdData.histogram.map((p) => ({
            time: p.time as import("lightweight-charts").UTCTimestamp,
            value: p.value,
            color: p.value >= 0 ? "rgba(16, 185, 129, 0.5)" : "rgba(239, 68, 68, 0.5)",
          }))
        );

        const macdLineSeries = chart.addSeries(LineSeries, {
          color: "#06b6d4",
          lineWidth: 1,
          priceLineVisible: false,
          lastValueVisible: false,
          priceScaleId: "macd",
        });
        macdLineSeries.setData(macdData.macdLine.map((p) => ({ time: p.time as import("lightweight-charts").UTCTimestamp, value: p.value })));

        const signalSeries = chart.addSeries(LineSeries, {
          color: "#f97316",
          lineWidth: 1,
          lineStyle: 2,
          priceLineVisible: false,
          lastValueVisible: false,
          priceScaleId: "macd",
        });
        signalSeries.setData(macdData.signalLine.map((p) => ({ time: p.time as import("lightweight-charts").UTCTimestamp, value: p.value })));
      }

      chart.timeScale().fitContent();
      indicatorChartRef.current = chart;
    };

    setupChart();

    const resizeObserver = new ResizeObserver(() => {
      if (indicatorChartRef.current && indicatorContainerRef.current) {
        indicatorChartRef.current.applyOptions({ width: indicatorContainerRef.current.clientWidth });
      }
    });
    resizeObserver.observe(indicatorContainerRef.current);

    return () => {
      resizeObserver.disconnect();
      if (chart) chart.remove();
      indicatorChartRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, candles]);

  return (
    <div className="wolf-card p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-white">{symbol}-USD</h2>
        <div className="flex items-center gap-2">
          {/* Timeframe buttons */}
          {TIMEFRAMES.map((tf) => (
            <button
              key={tf}
              onClick={() => handleTfChange(tf)}
              className={`px-2 py-1 rounded text-[10px] font-semibold transition ${
                timeframe === tf
                  ? "bg-[var(--wolf-emerald)]/20 text-[var(--wolf-emerald)]"
                  : "text-gray-500 hover:text-gray-300"
              }`}
            >
              {tf.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {/* Tab buttons */}
      <div className="flex items-center gap-1 mb-4 border-b border-[var(--border)] pb-2">
        {(["price", "volume", "indicators"] as TabKey[]).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-3 py-1.5 rounded-t text-xs font-semibold transition ${
              activeTab === tab
                ? "bg-[var(--surface)] text-white border-b-2 border-[var(--wolf-emerald)]"
                : "text-gray-500 hover:text-gray-300"
            }`}
          >
            {tab === "price" ? "Price" : tab === "volume" ? "Volume" : "RSI / MACD"}
          </button>
        ))}
        {activeTab === "price" && (
          <div className="ml-auto flex items-center gap-3 text-[10px]">
            <span className="text-[#f59e0b]">SMA20</span>
            <span className="text-[#8b5cf6]">SMA50</span>
            <span className="text-[#06b6d4]">EMA12</span>
            <span className="text-[rgba(139,92,246,0.5)]">BB(20,2)</span>
          </div>
        )}
      </div>

      {/* Chart containers */}
      {isLoading ? (
        <div className="h-[380px] flex items-center justify-center text-gray-500 text-sm">
          Loading chart data...
        </div>
      ) : ohlcData.length < 2 ? (
        <div className="h-[380px] flex items-center justify-center text-gray-500 text-sm border border-dashed border-[var(--border)] rounded-md">
          No chart data — start the intel service to fetch market data
        </div>
      ) : (
        <>
          <div ref={chartContainerRef} className={activeTab === "price" ? "" : "hidden"} />
          <div ref={volumeContainerRef} className={activeTab === "volume" ? "" : "hidden"} />
          <div ref={indicatorContainerRef} className={activeTab === "indicators" ? "" : "hidden"} />
        </>
      )}
    </div>
  );
}
