"""CLI: ``python -m gpodder_router <command>``."""
from __future__ import annotations

import argparse
import asyncio
import getpass
import sys

from gpodder_router.config import GPodderConfig
from gpodder_router.db import Database
from gpodder_router.exceptions import ConflictError
from gpodder_router.services import users as users_svc


def _config_from_args(args: argparse.Namespace) -> GPodderConfig:
    overrides: dict[str, object] = {}
    if args.database_url:
        overrides["database_url"] = args.database_url
    return GPodderConfig(**overrides)


async def _with_db(cfg: GPodderConfig):
    db = Database(cfg.database_url)
    await db.create_all()
    return db


async def cmd_create_user(args: argparse.Namespace) -> int:
    cfg = _config_from_args(args)
    password = args.password or getpass.getpass(f"Password for {args.username}: ")
    if not password:
        print("error: empty password", file=sys.stderr)
        return 2
    db = await _with_db(cfg)
    try:
        async with db.session() as session:
            try:
                user = await users_svc.create_user(
                    session,
                    username=args.username,
                    password=password,
                    email=args.email,
                    bcrypt_rounds=cfg.bcrypt_rounds,
                )
            except ConflictError as exc:
                print(f"error: {exc.detail}", file=sys.stderr)
                return 1
        print(f"created user {user.username!r} (id={user.id})")
        return 0
    finally:
        await db.dispose()


async def cmd_set_password(args: argparse.Namespace) -> int:
    cfg = _config_from_args(args)
    password = args.password or getpass.getpass(f"New password for {args.username}: ")
    if not password:
        print("error: empty password", file=sys.stderr)
        return 2
    db = await _with_db(cfg)
    try:
        async with db.session() as session:
            user = await users_svc.get_user(session, args.username)
            if user is None:
                print(f"error: user {args.username!r} not found", file=sys.stderr)
                return 1
            await users_svc.set_password(
                session, user, password, bcrypt_rounds=cfg.bcrypt_rounds
            )
        print(f"password updated for {args.username!r}")
        return 0
    finally:
        await db.dispose()


async def cmd_list_users(args: argparse.Namespace) -> int:
    from sqlalchemy import select
    from gpodder_router.db import User

    cfg = _config_from_args(args)
    db = await _with_db(cfg)
    try:
        async with db.session() as session:
            rows = list((await session.scalars(select(User).order_by(User.id))).all())
        if not rows:
            print("(no users)")
            return 0
        for u in rows:
            print(f"{u.id}\t{u.username}\t{u.email or ''}")
        return 0
    finally:
        await db.dispose()


async def cmd_delete_user(args: argparse.Namespace) -> int:
    cfg = _config_from_args(args)
    db = await _with_db(cfg)
    try:
        async with db.session() as session:
            user = await users_svc.get_user(session, args.username)
            if user is None:
                print(f"error: user {args.username!r} not found", file=sys.stderr)
                return 1
            await session.delete(user)
            await session.commit()
        print(f"deleted user {args.username!r}")
        return 0
    finally:
        await db.dispose()


async def cmd_init_db(args: argparse.Namespace) -> int:
    cfg = _config_from_args(args)
    db = Database(cfg.database_url)
    try:
        await db.create_all()
        print(f"schema ready at {cfg.database_url}")
        return 0
    finally:
        await db.dispose()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gpodder_router")
    parser.add_argument(
        "--database-url",
        help="SQLAlchemy async URL (overrides GPODDER_DATABASE_URL).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("create-user", help="Create a new user.")
    p.add_argument("username")
    p.add_argument("--password", help="Plain-text password (prompted if omitted).")
    p.add_argument("--email")
    p.set_defaults(func=cmd_create_user)

    p = sub.add_parser("set-password", help="Reset a user's password.")
    p.add_argument("username")
    p.add_argument("--password")
    p.set_defaults(func=cmd_set_password)

    p = sub.add_parser("delete-user", help="Delete a user (and their data).")
    p.add_argument("username")
    p.set_defaults(func=cmd_delete_user)

    p = sub.add_parser("list-users", help="List all users.")
    p.set_defaults(func=cmd_list_users)

    p = sub.add_parser("init-db", help="Create database schema.")
    p.set_defaults(func=cmd_init_db)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return asyncio.run(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
