"""PDF export service for pattern performance reports.

Generates professional PDF reports using ReportLab with pattern performance
metrics, sector breakdowns, and Wyckoff analysis.
"""

from io import BytesIO
from typing import TYPE_CHECKING, Optional

import structlog

if TYPE_CHECKING:
    from src.models.analytics import PatternPerformanceMetrics
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from src.models.analytics import PatternPerformanceResponse

logger = structlog.get_logger(__name__)


class PDFExportService:
    """Service for generating PDF reports from analytics data."""

    def __init__(self):
        """Initialize PDF export service."""
        self.styles = getSampleStyleSheet()
        self._add_custom_styles()

    def _add_custom_styles(self) -> None:
        """Add custom paragraph styles for report."""
        self.styles.add(
            ParagraphStyle(
                name="ReportTitle",
                parent=self.styles["Heading1"],
                fontSize=24,
                textColor=colors.HexColor("#1a1a1a"),
                spaceAfter=30,
                alignment=1,  # Center
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="SectionHeader",
                parent=self.styles["Heading2"],
                fontSize=16,
                textColor=colors.HexColor("#2c5aa0"),
                spaceBefore=20,
                spaceAfter=12,
            )
        )

    async def generate_performance_report(
        self,
        data: PatternPerformanceResponse,
        days: Optional[int] = None,
    ) -> bytes:
        """Generate PDF report from pattern performance data.

        Args:
            data: Pattern performance response data
            days: Time period in days (None = all time)

        Returns:
            PDF file as bytes
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18,
        )

        # Build report elements
        elements = []

        # Title
        title_text = self._get_title_text(days)
        elements.append(Paragraph(title_text, self.styles["ReportTitle"]))
        elements.append(Spacer(1, 0.3 * inch))

        # Metadata
        meta_text = f"Generated: {data.generated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}<br/>"
        meta_text += f"Cache Expires: {data.cache_expires_at.strftime('%Y-%m-%d %H:%M:%S UTC')}"
        elements.append(Paragraph(meta_text, self.styles["Normal"]))
        elements.append(Spacer(1, 0.3 * inch))

        # Summary Table
        elements.append(Paragraph("Pattern Performance Summary", self.styles["SectionHeader"]))
        elements.append(Spacer(1, 0.1 * inch))
        elements.append(self._create_summary_table(data))
        elements.append(Spacer(1, 0.3 * inch))

        # Individual Pattern Sections
        for pattern in data.patterns:
            elements.extend(self._create_pattern_section(pattern))

        # Sector Breakdown
        if data.sector_breakdown:
            elements.append(PageBreak())
            elements.append(Paragraph("Sector Performance Breakdown", self.styles["SectionHeader"]))
            elements.append(Spacer(1, 0.1 * inch))
            elements.append(self._create_sector_table(data.sector_breakdown))

        # Footer/Disclaimer
        elements.append(Spacer(1, 0.5 * inch))
        disclaimer = (
            "<i>Disclaimer: This report is for informational purposes only. "
            "Past performance does not guarantee future results. "
            "Trade at your own risk.</i>"
        )
        elements.append(Paragraph(disclaimer, self.styles["Normal"]))

        # Build PDF
        doc.build(elements)
        pdf_bytes = buffer.getvalue()
        buffer.close()

        logger.info(
            "PDF report generated",
            extra={"size_bytes": len(pdf_bytes), "pattern_count": len(data.patterns)},
        )

        return pdf_bytes

    def _get_title_text(self, days: Optional[int]) -> str:
        """Get report title based on time period."""
        if days is None:
            return "Pattern Performance Report - All Time"
        elif days == 7:
            return "Pattern Performance Report - Last 7 Days"
        elif days == 30:
            return "Pattern Performance Report - Last 30 Days"
        elif days == 90:
            return "Pattern Performance Report - Last 90 Days"
        else:
            return f"Pattern Performance Report - Last {days} Days"

    def _create_summary_table(self, data: PatternPerformanceResponse) -> Table:
        """Create summary table with all pattern metrics."""
        # Table header
        table_data = [["Pattern", "Win Rate", "Avg R", "Profit Factor", "Trade Count"]]

        # Add data rows
        for pattern in data.patterns:
            table_data.append(
                [
                    pattern.pattern_type,
                    f"{float(pattern.win_rate) * 100:.1f}%",
                    f"{float(pattern.average_r_multiple):.2f}",
                    f"{float(pattern.profit_factor):.2f}",
                    str(pattern.trade_count),
                ]
            )

        # Create table
        table = Table(
            table_data, colWidths=[1.5 * inch, 1 * inch, 1 * inch, 1.2 * inch, 1.2 * inch]
        )
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c5aa0")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 12),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
                ]
            )
        )
        return table

    def _create_pattern_section(self, pattern: "PatternPerformanceMetrics") -> list:
        """Create detailed section for individual pattern."""

        elements = []

        # Section header
        elements.append(
            Paragraph(f"{pattern.pattern_type} Pattern Analysis", self.styles["SectionHeader"])
        )
        elements.append(Spacer(1, 0.1 * inch))

        # Metrics table
        metrics_data = [
            ["Metric", "Value"],
            ["Win Rate", f"{float(pattern.win_rate) * 100:.2f}%"],
            ["Average R-Multiple", f"{float(pattern.average_r_multiple):.2f}"],
            ["Profit Factor", f"{float(pattern.profit_factor):.2f}"],
            ["Total Trades", str(pattern.trade_count)],
        ]

        # Add test quality metrics if available
        if pattern.test_confirmed_count > 0:
            metrics_data.append(["Test Confirmed Trades", str(pattern.test_confirmed_count)])
            if pattern.test_confirmed_win_rate is not None:
                metrics_data.append(
                    [
                        "Test Confirmed Win Rate",
                        f"{float(pattern.test_confirmed_win_rate) * 100:.1f}%",
                    ]
                )
            if pattern.non_test_confirmed_win_rate is not None:
                metrics_data.append(
                    [
                        "Non-Test Confirmed Win Rate",
                        f"{float(pattern.non_test_confirmed_win_rate) * 100:.1f}%",
                    ]
                )

        metrics_table = Table(metrics_data, colWidths=[3 * inch, 2 * inch])
        metrics_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4a7ba7")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
                ]
            )
        )
        elements.append(metrics_table)

        # Best/Worst trades if available
        if pattern.best_trade or pattern.worst_trade:
            elements.append(Spacer(1, 0.2 * inch))
            trades_text = ""
            if pattern.best_trade:
                trades_text += f"<b>Best Trade:</b> {pattern.best_trade.symbol} - "
                trades_text += f"{float(pattern.best_trade.r_multiple_achieved):.2f}R<br/>"
            if pattern.worst_trade:
                trades_text += f"<b>Worst Trade:</b> {pattern.worst_trade.symbol} - "
                trades_text += f"{float(pattern.worst_trade.r_multiple_achieved):.2f}R"
            elements.append(Paragraph(trades_text, self.styles["Normal"]))

        # Phase distribution if available
        if pattern.phase_distribution:
            elements.append(Spacer(1, 0.2 * inch))
            phase_text = "<b>Phase Distribution:</b><br/>"
            for phase, count in sorted(pattern.phase_distribution.items()):
                phase_text += f"&nbsp;&nbsp;• Phase {phase}: {count} trades<br/>"
            elements.append(Paragraph(phase_text, self.styles["Normal"]))

        elements.append(Spacer(1, 0.3 * inch))
        return elements

    def _create_sector_table(self, sectors: list) -> Table:
        """Create sector breakdown table."""
        # Table header
        table_data = [["Sector", "Win Rate", "Trade Count", "Avg R"]]

        # Add data rows (sorted by win rate descending)
        sorted_sectors = sorted(sectors, key=lambda s: s.win_rate, reverse=True)
        for sector in sorted_sectors:
            table_data.append(
                [
                    sector.sector_name,
                    f"{float(sector.win_rate) * 100:.1f}%",
                    str(sector.trade_count),
                    f"{float(sector.average_r_multiple):.2f}",
                ]
            )

        # Create table
        table = Table(table_data, colWidths=[2.5 * inch, 1.2 * inch, 1.2 * inch, 1 * inch])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c5aa0")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
                    # Highlight best sector (row 1) in green
                    ("BACKGROUND", (0, 1), (-1, 1), colors.lightgreen),
                    # Highlight worst sector (last row) in light red
                    ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#ffcccc")),
                ]
            )
        )
        return table
