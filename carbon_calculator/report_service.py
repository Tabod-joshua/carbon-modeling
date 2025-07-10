"""
Enhanced emission reporting: Generates visual charts and a PDF report then
sends it over email.  Relies on CarbonRecommendationService (LangChain).

NOTE: Sending email requires Django email backend to be configured (SMTP or
console).  For chart/PDF creation we use matplotlib and reportlab.
"""
from __future__ import annotations

import io
from typing import Dict, Any

import matplotlib.pyplot as plt

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib import colors

from .recommendation_service import CarbonRecommendationService


class EnhancedReportService:
    """High-level helper to generate a PDF & email it to the user."""

    def __init__(self) -> None:
        self.rec_service = CarbonRecommendationService()

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def generate_and_send_report(
        self,
        farm_data: Dict[str, Any],
        emissions: Dict[str, Any],
        benchmarks: Dict[str, float] | None = None,
        climate_zone: str | None = None,
    ) -> bytes:
        """Generates a PDF report and returns it as bytes."""
        try:
            benchmarks = benchmarks or {"average": 0.0, "best_quartile": 0.0}
            climate_zone = climate_zone or emissions.get("climate_zone", "unknown")

            print(f"[ReportService] Generating recommendations for farm: {farm_data.get('commune')}")
            recommendations = self.rec_service.generate_recommendations(
                farm_data, emissions, benchmarks, climate_zone
            )
            print(f"[ReportService] Generated recommendations: {recommendations[:100]}...") # Log first 100 chars
            
            print(f"[ReportService] Generating executive summary for farm: {farm_data.get('commune')}")
            summary = self.rec_service.generate_executive_summary(farm_data, emissions)
            print(f"[ReportService] Generated summary: {summary[:100]}...") # Log first 100 chars

            pdf_bytes = self._create_pdf_report(
                farm_data, emissions, recommendations, summary, benchmarks
            )
            return pdf_bytes
        except Exception as exc:  # pragma: no cover
            # Log the error – for brevity we just print here
            print(f"[ReportService] Error: {exc}")
            raise

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _create_visual_chart(self, emissions: Dict[str, Any]) -> bytes:
        """Return PNG image bytes for emission source split."""
        labels = []
        sizes = []
        
        # Ensure all emission sources are accounted for, even if 0
        emission_sources = {
            "Fertilizer": emissions.get("fertilizer", 0.0),
            "Livestock": emissions.get("livestock", {}).get("total", 0.0),
            "Fuel": emissions.get("fuel", 0.0),
            "Soil Carbon Change": emissions.get("soil_change", 0.0) # This is sequestration, so it can be negative
        }

        # Filter out zero values for cleaner chart, but include if all are zero
        non_zero_emissions = {k: v for k, v in emission_sources.items() if abs(v) > 0.01} # Use abs for soil_change

        if not non_zero_emissions:
            # If all are zero, show a default "No emissions" chart
            labels = ["No Significant Emissions"]
            sizes = [1]
            colors = ['#cccccc']
        else:
            labels = list(non_zero_emissions.keys())
            sizes = [abs(v) for v in non_zero_emissions.values()] # Use absolute values for pie chart
            
            # Define colors for consistency
            _colors = {
                "Fertilizer": '#ef4444', # Red
                "Livestock": '#f97316',  # Orange
                "Fuel": '#eab308',     # Yellow
                "Soil Carbon Change": '#22c55e' # Green
            }
            colors = [ _colors[label] for label in labels ]


        fig, ax = plt.subplots(figsize=(6, 6)) # Increased size for better clarity
        
        # Create pie chart
        wedges, texts, autotexts = ax.pie(
            sizes, 
            labels=labels, 
            autopct='%1.1f%%', 
            startangle=90, 
            colors=colors,
            pctdistance=0.85 # Position of percentage labels
        )
        
        # Draw a circle in the center to make it a doughnut chart
        centre_circle = plt.Circle((0,0),0.70,fc='white')
        fig.gca().add_artist(centre_circle)

        ax.axis('equal') # Equal aspect ratio ensures that pie is drawn as a circle.
        
        # Improve text appearance
        for text in texts:
            text.set_color('gray')
            text.set_fontsize(10)
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontsize(10)
            autotext.set_weight('bold')

        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches='tight', pad_inches=0.5) # Add padding and tight bbox
        plt.close(fig)
        return buf.getvalue()

    def _create_pdf_report(
        self,
        farm_data: Dict[str, Any],
        emissions: Dict[str, Any],
        recommendations: str,
        summary: str,
        benchmarks: Dict[str, float],
    ) -> bytes:
        """Return PDF as bytes."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()

        # Custom styles
        h1_style = styles['h1']
        h1_style.alignment = 1 # Center
        h1_style.spaceAfter = 14

        h2_style = styles['h2']
        h2_style.spaceBefore = 14
        h2_style.spaceAfter = 8

        h3_style = styles['h3']
        h3_style.spaceBefore = 10
        h3_style.spaceAfter = 6

        normal_style = styles['Normal']
        normal_style.spaceAfter = 6
        normal_style.leading = 14 # Line spacing

        story = []

        # Title
        story.append(Paragraph("Carbon Footprint Report", h1_style))
        story.append(Paragraph(f"Report for farm in {farm_data['commune']}", styles['h2']))
        story.append(Spacer(1, 0.2 * inch))

        # Executive Summary
        story.append(Paragraph("1. Executive Summary", h2_style))
        summary_text = f"This report provides a detailed analysis of the carbon footprint for a {farm_data['farm_size']:.1f}-hectare farm located in {farm_data['commune']}. The assessment, based on the IPCC 2019 methodology, reveals a net emission of {emissions['net_emissions']:.2f} kg CO2e per year. Key contributing factors include fertilizer application, livestock, and fuel consumption."
        story.append(Paragraph(summary_text, normal_style))
        story.append(Spacer(1, 0.2 * inch))

        # Emissions Breakdown
        story.append(Paragraph("2. Emissions Breakdown", h2_style))
        
        # Prepare data for the table
        table_data = [
            ['Source', 'Emissions (kg CO₂e/year)'],
            ['Fertilizer Application', f"{emissions.get('fertilizer', 0.0):.1f}"],
            ['Livestock (Enteric Fermentation)', f"{emissions.get('livestock', {}).get('enteric_fermentation', 0.0):.1f}"],
            ['Livestock (Manure Management)', f"{emissions.get('livestock', {}).get('manure_management', 0.0):.1f}"],
            ['Fuel Combustion', f"{emissions.get('fuel', 0.0):.1f}"],
            ['Soil Carbon Sequestration/Loss', f"{emissions.get('soil_change', 0.0):.1f}"],
            ['Total Net Emissions', f"{emissions.get('net_emissions', 0.0):.1f}"],
        ]

        # Table style
        table_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#166534')), # Header background
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke), # Header text color
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige), # Row background
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cccccc')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#166534')), # Border around table
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('LEFTPADDING', (0,0), (-1,-1), 6),
            ('RIGHTPADDING', (0,0), (-1,-1), 6),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ])

        emissions_table = Table(table_data, colWidths=[3.5*inch, 2.5*inch])
        emissions_table.setStyle(table_style)
        story.append(emissions_table)
        story.append(Spacer(1, 0.2 * inch))

        # Visual Chart
        story.append(Paragraph("Emissions Distribution", h3_style))
        chart_bytes = self._create_visual_chart(emissions)
        img = Image(io.BytesIO(chart_bytes), width=4*inch, height=4*inch)
        story.append(img)
        story.append(Spacer(1, 0.2 * inch))

        # Recommendations
        story.append(Paragraph("3. AI-Generated Recommendations", h2_style))
        for line in recommendations.split("\n"):
            if line.strip(): # Avoid adding empty paragraphs
                story.append(Paragraph(line, normal_style))
        story.append(Spacer(1, 0.2 * inch))

        # Build the PDF
        doc.build(story)
        buffer.seek(0)
        return buffer.read()

    
