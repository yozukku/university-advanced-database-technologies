package pl.edu.pk.ztb.bagazomat.opening;

import org.springframework.stereotype.Component;

/** @author Anton Gorokh */
@Component
class SimulatedDoorGateway {

	CellOpening.Result open(long openingId) {
		return CellOpening.Result.OPENED;
	}
}
