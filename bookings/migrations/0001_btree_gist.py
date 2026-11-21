"""Enable btree_gist BEFORE any model migration: the no-overlap ExclusionConstraint
mixes an equality on unit_id (btree) with a range overlap (GiST)."""
from django.contrib.postgres.operations import BtreeGistExtension
from django.db import migrations


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [BtreeGistExtension()]
