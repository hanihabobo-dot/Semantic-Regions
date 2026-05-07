"""
Shared fixtures for the Semantic Boxels regression tests.

Each test gets its own DIRECT PyBullet client (no GUI, no shared state),
plus small builders for BoxelData and an env / registry surrogate that
satisfies what compute_shadow_blockers reads from those objects.  The
real BoxelTestEnv / BoxelRegistry are heavy and load full scenes; the
audit #51 test only needs the narrow contract:

  - env.objects[name].object_id      (PyBullet body id lookup)
  - registry.get_boxel(boxel_id)     (BoxelData lookup)
"""
import numpy as np
import pybullet as p
import pytest

from boxel_data import BoxelData, BoxelType


@pytest.fixture
def pb_client():
    """Per-test DIRECT PyBullet client; disconnected on teardown."""
    cid = p.connect(p.DIRECT)
    yield cid
    p.disconnect(cid)


@pytest.fixture
def make_box_body(pb_client):
    """Factory: create a static box body at a given pose in the test client."""
    def _make(half_extents, position):
        cid = p.createCollisionShape(p.GEOM_BOX, halfExtents=half_extents)
        return p.createMultiBody(
            baseMass=0.0,
            baseCollisionShapeIndex=cid,
            basePosition=position,
        )
    return _make


@pytest.fixture
def shadow_boxel():
    """Factory: build a SHADOW BoxelData with a stale-AABB and parent link."""
    def _make(bid, min_corner, max_corner, parent):
        return BoxelData(
            id=bid,
            boxel_type=BoxelType.SHADOW,
            min_corner=np.array(min_corner, dtype=float),
            max_corner=np.array(max_corner, dtype=float),
            created_by_boxel_id=parent,
        )
    return _make


@pytest.fixture
def object_boxel():
    """
    Factory: build an OBJECT BoxelData with the given object_name.

    The stored AABB is intentionally a placeholder.  audit #51's fix
    reads p.getAABB(body_id) live from PyBullet, not the registry's
    stored corners — so the test must drive geometry via the body's
    pose, not via what we put on BoxelData.
    """
    def _make(bid, name):
        return BoxelData(
            id=bid,
            boxel_type=BoxelType.OBJECT,
            min_corner=np.array([-0.025, -0.025, -0.025]),
            max_corner=np.array([0.025, 0.025, 0.025]),
            object_name=name,
        )
    return _make


@pytest.fixture
def fake_env_and_registry():
    """
    Factory: (env, registry) surrogate pair with the minimum surface area
    that compute_shadow_blockers reads — env.objects[name].object_id and
    registry.get_boxel(bid).
    """
    class _Obj:
        def __init__(self, body_id):
            self.object_id = body_id

    class _Env:
        def __init__(self, bodies):
            self.objects = {n: _Obj(b) for n, b in bodies.items()}

    class _Reg:
        def __init__(self, boxels):
            self._b = {b.id: b for b in boxels}

        def get_boxel(self, bid):
            return self._b.get(bid)

    def _make(bodies, boxels):
        return _Env(bodies), _Reg(boxels)
    return _make
