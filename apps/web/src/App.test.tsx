import { render, screen } from "@testing-library/react";

import App from "./App";

test("renderiza o título", () => {
  render(<App />);
  expect(screen.getByRole("heading", { name: /tirei você/i })).toBeInTheDocument();
});
