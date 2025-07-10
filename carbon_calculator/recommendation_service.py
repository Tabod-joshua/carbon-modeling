"""
Service for generating carbon management recommendations using LangChain +
Ollama (Mistral model) with structured output validation.
"""
from __future__ import annotations

from typing import Dict, Any, Optional
import os
import json
import time
from datetime import datetime

try:
    from langchain_community.llms import Ollama
    from langchain_core.prompts import PromptTemplate
    from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
    from langchain_core.runnables import RunnablePassthrough
    from pydantic import BaseModel, Field, ValidationError
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "LangChain dependencies are missing. Install with `pip install langchain langchain-community pydantic`."
    ) from exc


class CarbonRecommendation(BaseModel):
    """Pydantic model for structured carbon recommendation output."""
    
    performance_assessment: str = Field(
        description="Assessment of farm performance compared to benchmarks and main emission sources"
    )
    
    priority_recommendations: list[str] = Field(
        description="List of 5 specific, actionable recommendations with expected impact",
        min_items=3,
        max_items=7
    )
    
    climate_smart_opportunities: list[str] = Field(
        description="List of climate-smart agriculture opportunities",
        min_items=3,
        max_items=5
    )
    
    carbon_market_potential: str = Field(
        description="Assessment of carbon market opportunities and potential revenue"
    )
    
    implementation_roadmap: Dict[str, list[str]] = Field(
        description="Implementation timeline with year1, year2_3, and long_term keys"
    )
    
    estimated_emission_reduction: float = Field(
        description="Estimated percentage reduction in emissions if recommendations are followed",
        ge=0.0,
        le=100.0
    )


class ExecutiveSummary(BaseModel):
    """Pydantic model for executive summary."""
    
    key_findings: str = Field(
        description="Main findings about the farm's carbon footprint"
    )
    
    primary_emission_sources: list[str] = Field(
        description="Top 2-3 emission sources identified",
        min_items=1,
        max_items=3
    )
    
    top_priority_action: str = Field(
        description="Single most important action to take immediately"
    )
    
    potential_savings: str = Field(
        description="Potential carbon and cost savings from recommendations"
    )


class CarbonRecommendationService:
    """Wraps a simple LangChain prompt pipeline to generate advisory reports."""

    def __init__(self) -> None:
        model_name = os.getenv("OLLAMA_MODEL", "mistral")
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.llm = Ollama(model=model_name, base_url=base_url, temperature=0.3)  # Lower temperature for more consistent output
        
        # Executive summary prompt
        self.summary_prompt = PromptTemplate(
            input_variables=[
                "farm_area", "crop_classes", "total_emissions", "fertilizer_emissions",
                "livestock_emissions", "fuel_emissions", "soil_carbon", "farm_type",
                "location", "livestock_details"
            ],
            template="""
You are an expert agricultural carbon consultant. Based on the farm data provided, generate a concise executive summary.

**Farm Details:**
- Location: {location}
- Total Area: {farm_area} hectares
- Farm Type: {farm_type}
- Crop Classes: {crop_classes}
- Livestock: {livestock_details}

**Carbon Footprint Analysis:**
- Total Annual Emissions: {total_emissions:.2f} tCO2e
- Fertilizer Emissions: {fertilizer_emissions:.2f} tCO2e
- Livestock Emissions: {livestock_emissions:.2f} tCO2e  
- Fuel/Energy Emissions: {fuel_emissions:.2f} tCO2e
- Soil Carbon: {soil_carbon:.2f} tCO2e

Return ONLY a valid JSON object with this exact structure:
{{
  "key_findings": "Brief overview of the farm's carbon performance and main insights",
  "primary_emission_sources": ["source1", "source2", "source3"],
  "top_priority_action": "Single most important recommendation for immediate implementation",
  "potential_savings": "Estimated carbon and cost reduction potential from recommendations"
}}

Ensure the JSON is valid and follows the exact structure above.
"""
        )

        # Main recommendations prompt  
        self.recommendations_prompt = PromptTemplate(
            input_variables=[
                "farm_area", "crop_classes", "total_emissions", "fertilizer_emissions",
                "livestock_emissions", "fuel_emissions", "soil_carbon", "farm_type",
                "location", "livestock_details", "emissions_per_hectare"
            ],
            template="""
You are an expert agricultural carbon consultant. Based on the farm data provided, generate 3-5 specific, actionable recommendations.

**Farm Details:**
- Location: {location}
- Total Area: {farm_area} hectares
- Farm Type: {farm_type}
- Crop Classes: {crop_classes}
- Livestock: {livestock_details}

**Carbon Footprint Analysis:**
- Total Annual Emissions: {total_emissions:.2f} tCO2e
- Emissions per Hectare: {emissions_per_hectare:.2f} tCO2e/ha
- Fertilizer Emissions: {fertilizer_emissions:.2f} tCO2e
- Livestock Emissions: {livestock_emissions:.2f} tCO2e  
- Fuel/Energy Emissions: {fuel_emissions:.2f} tCO2e
- Soil Carbon: {soil_carbon:.2f} tCO2e

Return ONLY a valid JSON array of recommendation objects with this exact structure:
[
  {{
    "title": "Specific action title",
    "description": "Detailed explanation of the recommendation and how to implement it",
    "category": "soil_management|fertilizer_optimization|livestock_management|energy_efficiency|crop_rotation",
    "impact_level": "high|medium|low",
    "implementation_timeframe": "immediate|short_term|long_term",
    "estimated_reduction_tco2e": 0.0,
    "estimated_cost_savings": "Cost savings description or amount"
  }}
]

Ensure the JSON is valid and follows the exact structure above. Provide 3-5 recommendations.
"""
        )

        # Setup chains with output parsers
        self.summary_chain = self.summary_prompt | self.llm
        self.recommendations_chain = self.recommendations_prompt | self.llm

        # Legacy prompt template (keeping for compatibility)
        self.prompt_template = PromptTemplate(
            input_variables=[
                "farm_size", "commune", "farming_practice", "crop_classes",
                "total_emissions", "emissions_per_hectare", "fuel_emissions",
                "fertilizer_emissions", "livestock_emissions", "soil_change",
                "regional_average", "best_quartile", "climate_zone"
            ],
            template="""
You are an expert agricultural carbon consultant specializing in Sub-Saharan Africa.
FARM ANALYSIS FOR CAMEROON:

Farm Details:
- Location: {commune}, Cameroon
- Size: {farm_size} hectares
- Farming System: {farming_practice}
- Crop Types: {crop_classes}
- Climate Zone: {climate_zone}

Carbon Emissions Breakdown:
- Total Annual Emissions: {total_emissions:.1f} kg CO₂e
- Emissions per Hectare: {emissions_per_hectare:.1f} kg CO₂e/ha
- Fuel/Machinery: {fuel_emissions:.1f} kg CO₂e
- Fertilizer (N₂O): {fertilizer_emissions:.1f} kg CO₂e
- Livestock (CH₄): {livestock_emissions:.1f} kg CO₂e
- Soil Carbon Change: {soil_change:.1f} kg CO₂e (negative = sequestration)

Regional Benchmarks:
- Regional Average: {regional_average:.1f} kg CO₂e/ha
- Best Performing Farms: {best_quartile:.1f} kg CO₂e/ha

Provide a comprehensive analysis with:

1. PERFORMANCE ASSESSMENT:
- Compare farm performance to regional benchmarks
- Identify main emission sources and their significance
- Assess carbon sequestration potential
- Analyze the multi-crop system impact on emissions

2. PRIORITY RECOMMENDATIONS (Top 5):
- Specific, actionable practices suitable for Cameroon
- Crop rotation and intercropping strategies
- Expected emission reductions (quantified where possible)
- Implementation timeline and costs
- Local resource requirements

3. CLIMATE-SMART AGRICULTURE OPPORTUNITIES:
- Drought-resistant crop varieties for each crop type
- Water conservation techniques
- Soil health improvement strategies
- Integrated pest management across multiple crops

4. CARBON MARKET OPPORTUNITIES:
- Potential for carbon credit generation
- Certification requirements
- Expected revenue streams
- Risk assessment

5. IMPLEMENTATION ROADMAP:
- Year 1 priorities
- Medium-term goals (2-3 years)
- Long-term vision (5+ years)
- Monitoring and verification needs

Format your response as a professional agricultural advisory report.
Focus on practical, cost-effective solutions appropriate for small-scale farmers in Cameroon.
Address the complexity of managing multiple crop types simultaneously.
"""
        )

        self.chain = RunnablePassthrough() | self.prompt_template | self.llm | StrOutputParser()

    # ---------------------------------------------------------------------
    # Public helpers
    # ---------------------------------------------------------------------

    def generate_recommendations(
        self,
        farm_data: Dict[str, Any],
        emissions: Dict[str, Any],
        benchmarks: Dict[str, float] | None = None,
        climate_zone: str | None = None,
    ) -> str:
        """Return rich text advisory report generated by the LLM."""
        benchmarks = benchmarks or {"average": 0.0, "best_quartile": 0.0}
        climate_zone = climate_zone or "unknown"

        # Handle both new crop_classes and legacy crop_class
        crop_classes = farm_data.get("crop_classes", [])
        if not crop_classes and "crop_class" in farm_data:
            crop_classes = [farm_data["crop_class"]]
        
        # Convert crop_classes list to readable string
        crop_classes_str = ", ".join(crop_classes) if crop_classes else "Unknown"
        
        chain_input = {
            "farm_size": farm_data["farm_size"],
            "commune": farm_data["commune"],
            "farming_practice": farm_data["farming_practice"],
            "crop_classes": crop_classes_str,
            "total_emissions": emissions["total_net"],
            "emissions_per_hectare": emissions["total_net"] / farm_data["farm_size"],
            "fuel_emissions": emissions["fuel"],
            "fertilizer_emissions": emissions["fertilizer"],
            "livestock_emissions": emissions["livestock"]["total"],
            "soil_change": emissions["soil_change"],
            "regional_average": benchmarks.get("average", 0.0),
            "best_quartile": benchmarks.get("best_quartile", 0.0),
            "climate_zone": climate_zone,
        }
        return self.chain.invoke(chain_input)

    def generate_executive_summary(self, farm_data: Dict, emissions: Dict) -> str:
        """Return 3-sentence summary of results."""
        summary_prompt = PromptTemplate(
            input_variables=["farm_size", "total_emissions", "main_sources"],
            template=(
                """
            Create a 3-sentence executive summary for a carbon footprint analysis:\n\n            Farm: {farm_size} hectares\n            Total Emissions: {total_emissions:.1f} kg CO₂e/year\n            Main Sources: {main_sources}\n\n            Focus on key findings and top priority action.\n            """
            ),
        )

        sources = []
        if emissions["fuel"] > 0:
            sources.append("machinery fuel")
        if emissions["fertilizer"] > 0:
            sources.append("fertiliser application")
        if emissions["livestock"]["total"] > 0:
            sources.append("livestock")

        main_sources = ", ".join(sources) if sources else "minimal sources"

        summary_chain = summary_prompt | self.llm | StrOutputParser()
        return summary_chain.invoke(
            {
                "farm_size": farm_data["farm_size"],
                "total_emissions": emissions["total_net"],
                "main_sources": main_sources,
            }
        ) 