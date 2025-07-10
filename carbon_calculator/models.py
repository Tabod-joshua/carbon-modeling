from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid


class CarbonCalculation(models.Model):
    """
    Model to store carbon footprint calculation results and farm data.
    """
    # Unique identifier for each calculation
    calculation_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    
    # Farm information
    farm_size = models.FloatField(
        validators=[MinValueValidator(0.1)],
        help_text="Farm size in hectares"
    )
    commune = models.CharField(max_length=100, help_text="Commune location in Cameroon")
    farming_practice = models.CharField(
        max_length=50,
        choices=[
            ('conventional', 'Conventional'),
            ('organic', 'Organic'),
            ('agroforestry', 'Agroforestry'),
            ('conservation', 'Conservation'),
            ('mixed', 'Mixed'),
        ],
        default='conventional'
    )
    
    # Crop information
    crop_classes = models.JSONField(
        default=list,
        help_text="List of crop classes grown on the farm"
    )
    
    # Fertilizer information
    fertilizer_type = models.CharField(
        max_length=20,
        choices=[
            ('none', 'None'),
            ('organic', 'Organic'),
            ('synthetic', 'Synthetic'),
            ('both', 'Both'),
        ],
        default='none'
    )
    fertilizer_rate = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0)],
        help_text="Fertilizer application rate in kg/ha"
    )
    
    # Field management
    tillage_practice = models.CharField(
        max_length=30,
        choices=[
            ('conventional_till', 'Conventional Tillage'),
            ('reduced_till', 'Reduced Tillage'),
            ('no_till', 'No-Till'),
        ],
        default='conventional_till'
    )
    irrigation = models.CharField(
        max_length=3,
        choices=[('yes', 'Yes'), ('no', 'No')],
        default='no'
    )
    
    # Machinery and fuel
    uses_machinery = models.BooleanField(default=False)
    fuel_consumption = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0)],
        help_text="Monthly fuel consumption in liters"
    )
    
    # Livestock
    keeps_livestock = models.BooleanField(default=False)
    livestock_counts = models.JSONField(
        default=dict,
        help_text="Livestock counts by animal type"
    )
    
    # Contact information
    
    
    # Environmental data (from APIs)
    coordinates = models.JSONField(
        default=dict,
        help_text="Latitude and longitude coordinates"
    )
    weather_data = models.JSONField(
        default=dict,
        help_text="Weather data from external API"
    )
    soil_data = models.JSONField(
        default=dict,
        help_text="Soil data from external API"
    )
    climate_zone = models.CharField(max_length=50, blank=True)
    
    # Calculation results
    total_emissions = models.FloatField(
        help_text="Total gross emissions in kg CO2e per year"
    )
    net_emissions = models.FloatField(
        help_text="Net emissions (after soil carbon sequestration) in kg CO2e per year"
    )
    emissions_per_hectare = models.FloatField(
        help_text="Emissions per hectare in kg CO2e/ha/year"
    )
    
    # Detailed emissions breakdown
    fertilizer_emissions = models.FloatField(default=0.0)
    livestock_emissions = models.FloatField(default=0.0)
    fuel_emissions = models.FloatField(default=0.0)
    soil_carbon_sequestration = models.FloatField(default=0.0)
    
    # Carbon intensity classification
    carbon_intensity = models.CharField(
        max_length=20,
        choices=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('very_high', 'Very High'),
        ],
        blank=True
    )
    
    # Recommendations and report
    recommendations_generated = models.BooleanField(default=False)
    
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Carbon Calculation"
        verbose_name_plural = "Carbon Calculations"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['commune']),
            
            models.Index(fields=['carbon_intensity']),
        ]
    
    def __str__(self):
        return f"Calculation for {self.commune} - {self.farm_size}ha ({self.created_at.strftime('%Y-%m-%d')})"
    
    @property
    def total_livestock_count(self):
        """Return total number of livestock across all types."""
        return sum(self.livestock_counts.values()) if self.livestock_counts else 0
    
    @property
    def emissions_reduction_potential(self):
        """Calculate potential emissions reduction percentage."""
        if self.carbon_intensity == 'low':
            return 5
        elif self.carbon_intensity == 'medium':
            return 15
        elif self.carbon_intensity == 'high':
            return 25
        else:  # very_high
            return 35


class RecommendationLog(models.Model):
    """
    Model to store AI-generated recommendations for each calculation.
    """
    calculation = models.OneToOneField(
        CarbonCalculation,
        on_delete=models.CASCADE,
        related_name='recommendation_log'
    )
    
    # LLM-generated content
    executive_summary = models.TextField(help_text="3-sentence executive summary")
    detailed_recommendations = models.TextField(help_text="Full AI-generated recommendations")
    
    # Generation metadata
    model_used = models.CharField(max_length=50, default='mistral')
    generation_time_seconds = models.FloatField(null=True, blank=True)
    tokens_used = models.IntegerField(null=True, blank=True)
    
    # Quality metrics
    recommendations_quality_score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Quality score from 0-1 based on content analysis"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Recommendation Log"
        verbose_name_plural = "Recommendation Logs"
    
    def __str__(self):
        return f"Recommendations for {self.calculation.commune} ({self.created_at.strftime('%Y-%m-%d')})"



