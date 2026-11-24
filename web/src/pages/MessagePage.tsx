import { Button, Card } from "@mantine/core";
import type { Icon } from "@tabler/icons-react";
import { Link } from "react-router-dom";

import { EmptyState } from "../ui";

export function MessagePage({ icon, title, text }: { icon: Icon; title: string; text: string }) {
  return (
    <Card mt="xl">
      <EmptyState
        icon={icon}
        title={title}
        action={
          <Button component={Link} to="/" variant="light">
            Go to your dashboard
          </Button>
        }
      >
        {text}
      </EmptyState>
    </Card>
  );
}
