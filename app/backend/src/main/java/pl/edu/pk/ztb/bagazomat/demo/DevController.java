package pl.edu.pk.ztb.bagazomat.demo;

import org.springframework.context.annotation.Profile;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import pl.edu.pk.ztb.bagazomat.shipment.IncomingShipment;

/** @author Anton Gorokh */
@RestController
@Profile("dev")
@RequestMapping("/api/dev")
class DevController {

	private final DemoService demoService;
	private final ShipmentSimulator shipmentSimulator;

	DevController(DemoService demoService, ShipmentSimulator shipmentSimulator) {
		this.demoService = demoService;
		this.shipmentSimulator = shipmentSimulator;
	}

	@PostMapping("/reset")
	@ResponseStatus(HttpStatus.NO_CONTENT)
	public void reset() {
		demoService.reset();
	}

	@PostMapping("/shipments")
	@ResponseStatus(HttpStatus.CREATED)
	public IncomingShipment simulateShipment(@AuthenticationPrincipal Jwt jwt) {
		return shipmentSimulator.simulate(jwt);
	}
}
