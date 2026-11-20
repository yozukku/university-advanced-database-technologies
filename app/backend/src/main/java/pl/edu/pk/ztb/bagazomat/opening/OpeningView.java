package pl.edu.pk.ztb.bagazomat.opening;

import pl.edu.pk.ztb.bagazomat.access.AccessCode;

/** @author Anton Gorokh */
record OpeningView(Long id, AccessCode.Purpose purpose, CellOpening.Result result) {
}
