package com.chessaiarena.api.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.reactive.function.client.WebClient;

@Configuration
public class RateClientConfig {

  @Bean
  public WebClient rateWebClient(@Value("${rate.base-url}") String baseUrl) {
    return WebClient.builder().baseUrl(baseUrl).build();
  }
}
