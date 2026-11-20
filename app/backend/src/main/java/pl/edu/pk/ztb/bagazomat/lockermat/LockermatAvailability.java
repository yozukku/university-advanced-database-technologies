package pl.edu.pk.ztb.bagazomat.lockermat;

import java.math.BigDecimal;
import java.util.List;

/** @author Anton Gorokh */
record LockermatAvailability(long id, String name, String address, double lng, double lat, List<SizeAvailability> sizes) {

	record SizeAvailability(CellSize size, long free, BigDecimal price) {
	}
}
