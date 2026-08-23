from typing import List, Tuple
from pydantic import BaseModel, Field

class Point2D(BaseModel):
    x: float
    y: float

class BoundingBox(BaseModel):
    """Representación de caja delimitadora normalizada [0.0 - 1.0]."""
    x0: float = Field(..., ge=0.0, le=1.0)
    y0: float = Field(..., ge=0.0, le=1.0)
    x1: float = Field(..., ge=0.0, le=1.0)
    y1: float = Field(..., ge=0.0, le=1.0)

    @property
    def width(self) -> float:
        return max(0.0, self.x1 - self.x0)

    @property
    def height(self) -> float:
        return max(0.0, self.y1 - self.y0)

    @property
    def center(self) -> Tuple[float, float]:
        return ((self.x0 + self.x1) / 2.0, (self.y0 + self.y1) / 2.0)

    def to_list(self) -> List[float]:
        return [self.x0, self.y0, self.x1, self.y1]

    def to_absolute_pixels(self, img_width: int, img_height: int) -> Tuple[int, int, int, int]:
        """Convierte coordenadas normalizadas a píxeles enteros."""
        return (
            int(self.x0 * img_width),
            int(self.y0 * img_height),
            int(self.x1 * img_width),
            int(self.y1 * img_height),
        )

class Polygon2D(BaseModel):
    """Polígono 2D arbitrario definido por una lista de vértices normalizados."""
    points: List[Point2D]

    def to_points_list(self) -> List[List[float]]:
        return [[p.x, p.y] for p in self.points]
