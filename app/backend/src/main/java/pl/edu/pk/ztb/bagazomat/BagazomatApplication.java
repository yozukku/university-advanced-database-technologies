package pl.edu.pk.ztb.bagazomat;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

/** @author Anton Gorokh */
@SpringBootApplication
@EnableScheduling
public class BagazomatApplication {

	public static void main(String[] args) {
		SpringApplication.run(BagazomatApplication.class, args);
	}
}
