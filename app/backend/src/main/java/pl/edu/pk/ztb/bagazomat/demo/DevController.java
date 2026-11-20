package pl.edu.pk.ztb.bagazomat.demo;

import org.springframework.context.annotation.Profile;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

/** @author Anton Gorokh */
@RestController
@Profile("dev")
@RequestMapping("/api/dev")
class DevController {

	private final DemoService demoService;

	DevController(DemoService demoService) {
		this.demoService = demoService;
	}

	@PostMapping("/reset")
	@ResponseStatus(HttpStatus.NO_CONTENT)
	public void reset() {
		demoService.reset();
	}
}
