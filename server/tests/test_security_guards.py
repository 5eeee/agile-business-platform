import asyncio
import uuid
import unittest
from types import SimpleNamespace

from fastapi import HTTPException
from starlette.requests import Request

from app.api.admin import _protect_role_hierarchy
from app.api.auth import setup_totp
from app.api.gamification import router as gamification_router
from app.models.user import UserRole
from app.rate_limit import _get_real_ip
from app.services.s3 import ALLOWED_EXTENSIONS


def _request(headers: list[tuple[bytes, bytes]]) -> Request:
    return Request({
        "type": "http",
        "method": "POST",
        "path": "/api/auth/login",
        "headers": headers,
        "client": ("10.0.0.5", 12345),
    })


class SecurityGuardTests(unittest.TestCase):
    def test_rate_limit_uses_proxy_appended_address(self):
        request = _request([(b"x-forwarded-for", b"1.2.3.4, 203.0.113.9")])
        self.assertEqual(_get_real_ip(request), "203.0.113.9")

    def test_svg_uploads_are_not_allowed(self):
        self.assertNotIn("svg", ALLOWED_EXTENSIONS)

    def test_regular_admin_cannot_promote_or_modify_owner(self):
        admin = SimpleNamespace(id=uuid.uuid4(), role=UserRole.ADMIN)
        employee = SimpleNamespace(id=uuid.uuid4(), role=UserRole.USER)
        owner = SimpleNamespace(id=uuid.uuid4(), role=UserRole.OWNER)
        with self.assertRaises(HTTPException):
            _protect_role_hierarchy(admin, employee, {"role": "admin"})
        with self.assertRaises(HTTPException):
            _protect_role_hierarchy(admin, owner, {"status": "blocked"})

    def test_enabled_2fa_secret_cannot_be_replaced(self):
        user = SimpleNamespace(totp_enabled=True)
        with self.assertRaises(HTTPException) as caught:
            asyncio.run(setup_totp(user=user, db=None))
        self.assertEqual(caught.exception.status_code, 409)

    def test_kpi_review_route_requires_admin_dependency(self):
        route = next(route for route in gamification_router.routes if route.path == "/gamification/kpi/reviews")
        dependencies = {dependency.call.__name__ for dependency in route.dependant.dependencies}
        self.assertIn("require_admin", dependencies)


if __name__ == "__main__":
    unittest.main()
