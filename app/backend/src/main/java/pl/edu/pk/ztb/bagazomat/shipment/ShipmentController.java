package pl.edu.pk.ztb.bagazomat.shipment;

import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/** @author Anton Gorokh */
@RestController
class ShipmentController {

	private final ShipmentService shipmentService;

	ShipmentController(ShipmentService shipmentService) {
		this.shipmentService = shipmentService;
	}

	@GetMapping("/api/shipments/incoming")
	public List<IncomingShipment> findIncoming(@AuthenticationPrincipal Jwt jwt) {
		return shipmentService.findIncoming(jwt);
	}
}
