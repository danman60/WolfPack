"""Execution Timing — Optimal entry/exit timing based on volume and volatility patterns."""

from pydantic import BaseModel


class ExecutionWindow(BaseModel):
    optimal_hours_utc: list[int]
    current_quality: str  # "excellent", "good", "fair", "poor"
    volume_relative: float  # Current volume vs average (1.0 = average)
    reason: str


class ExecutionTiming:
    """
    Analyzes historical volume and volatility patterns to recommend
    optimal execution windows, minimizing slippage.
    """

    # Typical crypto volume peaks (UTC hours)
    PEAK_HOURS = [14, 15, 16, 17, 18, 19, 20]  # US market overlap
    LOW_HOURS = [2, 3, 4, 5, 6]  # Asia quiet hours

    def analyze(self, hourly_volumes: list[float], current_hour_utc: int) -> ExecutionWindow:
        if not hourly_volumes:
            return ExecutionWindow(
                optimal_hours_utc=self.PEAK_HOURS,
                current_quality="unknown",
                volume_relative=1.0,
                reason="No volume data available",
            )

        avg_vol = sum(hourly_volumes) / len(hourly_volumes) if hourly_volumes else 1
        current_vol = hourly_volumes[-1] if hourly_volumes else 0
        vol_relative = current_vol / avg_vol if avg_vol > 0 else 1.0

        if current_hour_utc in self.PEAK_HOURS and vol_relative > 0.8:
            quality = "excellent"
            reason = "Peak trading hours with healthy volume"
        elif vol_relative > 1.2:
            quality = "good"
            reason = "Above-average volume"
        elif current_hour_utc in self.LOW_HOURS:
            quality = "poor"
            reason = "Low activity hours — higher spread likely"
        else:
            quality = "fair"
            reason = "Normal conditions"

        return ExecutionWindow(
            optimal_hours_utc=self.PEAK_HOURS,
            current_quality=quality,
            volume_relative=round(vol_relative, 2),
            reason=reason,
        )
