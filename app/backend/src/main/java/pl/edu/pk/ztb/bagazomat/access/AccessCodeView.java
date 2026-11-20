package pl.edu.pk.ztb.bagazomat.access;

import java.time.Instant;

/** @author Anton Gorokh */
record AccessCodeView(AccessCode.Purpose purpose, String pin, Instant validFrom, Instant validTo) {
}
