package pl.edu.pk.ztb.bagazomat.security;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.context.annotation.Import;
import org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders;
import org.springframework.test.web.servlet.request.RequestPostProcessor;
import org.springframework.test.web.servlet.result.MockMvcResultMatchers;
import pl.edu.pk.ztb.bagazomat.PostgresContainerConfiguration;

import java.util.UUID;

/** @author Anton Gorokh */
@SpringBootTest
@AutoConfigureMockMvc
@Import(PostgresContainerConfiguration.class)
class ApiAccessTests {

	private static final String ANNA = "900f9895-3b4d-5e82-a35f-ad11c64f9f00";

	@Autowired
	private MockMvc mockMvc;

	@Test
	void letsSeededCustomerIn() throws Exception {
		mockMvc.perform(MockMvcRequestBuilders.get("/api/me").with(tokenFor(ANNA)))
				.andExpect(MockMvcResultMatchers.status().isOk());
	}

	@Test
	void forbidsTokenWithUnknownSubject() throws Exception {
		mockMvc.perform(MockMvcRequestBuilders.get("/api/me").with(tokenFor(UUID.randomUUID().toString())))
				.andExpect(MockMvcResultMatchers.status().isForbidden());
	}

	@Test
	void rejectsRequestWithoutToken() throws Exception {
		mockMvc.perform(MockMvcRequestBuilders.get("/api/me"))
				.andExpect(MockMvcResultMatchers.status().isUnauthorized());
	}

	@Test
	void hidesResetOutsideDevProfile() throws Exception {
		mockMvc.perform(MockMvcRequestBuilders.post("/api/dev/reset").with(tokenFor(ANNA)).with(SecurityMockMvcRequestPostProcessors.csrf()))
				.andExpect(MockMvcResultMatchers.status().isNotFound());
	}

	private RequestPostProcessor tokenFor(String subject) {
		return SecurityMockMvcRequestPostProcessors.jwt().jwt(jwt -> jwt.subject(subject));
	}
}
