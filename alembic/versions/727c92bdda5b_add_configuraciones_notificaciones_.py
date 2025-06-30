"""Add configuraciones_notificaciones table only

Revision ID: 727c92bdda5b
Revises: bc964be15d45
Create Date: 2025-06-29 20:35:24.830644

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '727c92bdda5b'
down_revision: Union[str, Sequence[str], None] = 'bc964be15d45'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
