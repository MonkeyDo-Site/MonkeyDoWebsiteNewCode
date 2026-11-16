LABELS = ("Choose Session", "Customer Details", "Session Details", "Payment Details")


def progress(step, *, done=False):
    return [
        {
            "number": i,
            "label": label,
            "active": not done and i == step,
            "complete": done or i < step,
        }
        for i, label in enumerate(LABELS, 1)
    ]
