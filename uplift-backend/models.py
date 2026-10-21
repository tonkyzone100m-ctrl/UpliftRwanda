"""SQLAlchemy data models for UpliftRwanda (NISR 2026 Big Data Hackathon).

Schema layout (mirrors the API contract used by the React dashboard):

    regions          one row per Rwandan district (30 total)
    indicators       canonical catalog of FinScope 2024 / EICV7 indicators
    survey_metrics   long/tidy fact table: one observation per
                     (district x indicator x survey year)

All column types are kept cross-database (works on PostgreSQL AND SQLite) so the
seed script can be rehearsed locally against SQLite before hitting PostgreSQL.
"""

from sqlalchemy import Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Region(Base):
    """A Rwandan district (province + area classification)."""

    __tablename__ = "regions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    province: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    district: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    area_type: Mapped[str] = mapped_column(String(16), nullable=False, default="rural")
    population_weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    metrics: Mapped[list["SurveyMetric"]] = relationship(
        back_populates="region", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<Region {self.district} ({self.province})>"


class Indicator(Base):
    """Canonical FinScope 2024 / EICV7 indicator definition."""

    __tablename__ = "indicators"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    indicator_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    indicator_name: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    unit: Mapped[str] = mapped_column(String(24), nullable=False, default="%")
    description: Mapped[str] = mapped_column(String(256), nullable=False, default="")

    metrics: Mapped[list["SurveyMetric"]] = relationship(
        back_populates="indicator", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<Indicator {self.indicator_code}>"


class SurveyMetric(Base):
    """One observed value for (district, indicator, survey year)."""

    __tablename__ = "survey_metrics"
    __table_args__ = (
        UniqueConstraint(
            "region_id",
            "indicator_id",
            "survey_year",
            name="uq_metric_region_indicator_year",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    region_id: Mapped[int] = mapped_column(
        ForeignKey("regions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    indicator_id: Mapped[int] = mapped_column(
        ForeignKey("indicators.id", ondelete="CASCADE"), nullable=False, index=True
    )
    survey_year: Mapped[int] = mapped_column(Integer, nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)

    region: Mapped[Region] = relationship(back_populates="metrics")
    indicator: Mapped[Indicator] = relationship(back_populates="metrics")

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<SurveyMetric region={self.region_id} indicator={self.indicator_id} year={self.survey_year} value={self.value}>"


class DistrictCfsvaMetrics(Base):
    """CFSVA 2024 food-security & nutrition layer (separate from FinScope).

    NON-DESTRUCTIVE integration: a new table keyed on the SAME `regions.id`
    values; no existing table/column is altered. One row per district per
    survey wave (unique together on region + year).
    """

    __tablename__ = "district_cfsva_metrics"
    __table_args__ = (
        UniqueConstraint("region_id", "survey_year", name="uq_cfsva_region_year"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    region_id: Mapped[int] = mapped_column(
        ForeignKey("regions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    survey_year: Mapped[int] = mapped_column(Integer, nullable=False)

    # Food security & consumption (WFP/IPC scale)
    fies_moderate_severe_pct: Mapped[float] = mapped_column(Float, nullable=False)   # moderate+severe food insecurity, %
    fies_severe_pct: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)  # severely food insecure, %
    food_consumption_score: Mapped[float] = mapped_column(Float, nullable=False)    # mean FCS, 0-112 pts
    fcs_poor_pct: Mapped[float] = mapped_column(Float, nullable=False)             # share with poor FCS, %
    # Dietary diversity
    hdds: Mapped[float] = mapped_column(Float, nullable=False)                     # mean HDDS, 0-12
    # Malnutrition (children under 5)
    stunting_pct: Mapped[float] = mapped_column(Float, nullable=False)
    wasting_pct: Mapped[float] = mapped_column(Float, nullable=False)
    # Agricultural vulnerability / stress
    rcsi: Mapped[float] = mapped_column(Float, nullable=False)                     # reduced coping strategies index
    harvest_loss_pct: Mapped[float] = mapped_column(Float, nullable=False)         # hh with >=1 harvest loss, %

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<DistrictCfsvaMetrics region={self.region_id} year={self.survey_year}>"
