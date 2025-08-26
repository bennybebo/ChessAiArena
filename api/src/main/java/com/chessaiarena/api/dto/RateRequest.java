package com.chessaiarena.api.dto;

import jakarta.validation.constraints.Size;

public record RateRequest(
  @Size(max = 10_000_000) String pgnText, // one of pgnText or pgnUrl must be provided
  String pgnUrl
) {}
