from dataclasses import dataclass

from faker import Faker


@dataclass(frozen=True)
class Person:
    name: str
    email: str
    phone: str


@dataclass(frozen=True)
class Company:
    name: str
    address: str


def person_pools(profile, customers=4096, recipients=4096):
    fake = Faker("pl_PL")
    fake.seed_instance(profile.seed)
    return make_pool(fake, "500", customers), make_pool(fake, "501", recipients)


def make_pool(fake, prefix, count):
    return tuple(
        Person(fake.name(), f"{fake.user_name().lower()}.{prefix}{index}@example.test", f"+48{prefix}{index:06d}")
        for index in range(count)
    )


def company_pool(profile, count):
    fake = Faker("pl_PL")
    fake.seed_instance(profile.seed + 1)
    return tuple(Company(fake.company(), fake.address().replace("\n", ", ")) for _ in range(count))
