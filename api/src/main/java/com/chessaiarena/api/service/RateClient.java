package com.chessaiarena.api.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.chessaiarena.api.dto.RateRequest;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
//import reactor.core.publisher.Mono;

@Service
public class RateClient {

  private final WebClient webClient;

  public RateClient(WebClient rateWebClient) {
    this.webClient = rateWebClient;
  }

  public JsonNode rate(RateRequest req) {
    // Forward to Python worker: POST /rate with either pgn_text or pgn_path
    var payload = new java.util.HashMap<String,Object>();
    if (req.pgnText() != null && !req.pgnText().isBlank()) payload.put("pgn_text", req.pgnText());
    if (req.pgnUrl()  != null && !req.pgnUrl().isBlank())  payload.put("pgn_path", req.pgnUrl());

    return webClient.post()
      .uri("/rate")
      .contentType(MediaType.APPLICATION_JSON)
      .bodyValue(payload)
      .retrieve()
      .bodyToMono(JsonNode.class)
      .block(); // simple for now; you can make the controller reactive later
  }
}
