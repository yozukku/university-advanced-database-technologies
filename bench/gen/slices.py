def unused_lockers(count):
    return max(1, count // 100)


def exact_slices(profile, plan):
    return {
        "unreferenced customers": plan.counts["customer_"] // 20,
        "unused lockers": unused_lockers(plan.counts["lockermat_"]),
        "overdue occupied legs": sum(count // 2 for cohort, count in plan.cohorts if "OCCUPIED" in cohort.legs),
        "unpaid orders past deadline": sum(count - count // 10 for cohort, count in plan.cohorts
                                           if cohort.status == "AWAITING_PAYMENT"),
        "expired active codes": plan.counts["access_code_"] // 20,
        "pending openings": profile.pending_openings,
    }
