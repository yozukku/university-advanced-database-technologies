from dataclasses import dataclass

from faker import Faker


@dataclass(frozen=True)
class Person:
    name: str
    email: str
    phone: str


def person_pools(profile, count=4096):
    fake = Faker("pl_PL")
    fake.seed_instance(profile.seed)
    customers = make_pool(fake, "500", count)
    recipients = make_pool(fake, "501", count)
    return customers, recipients


def make_pool(fake, prefix, count):
    return tuple(
        Person(fake.name(), f"{fake.user_name().lower()}.{prefix}{index}@example.test", f"+48{prefix}{index:06d}")
        for index in range(count)
    )
