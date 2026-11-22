LABELS = ("Choose Session", "Customer Details", "Session Details", "Payment Details")


def progress(step, *, done=False, waivers=False):
    labels = LABELS[:3] + ("Waiver Details",) + LABELS[3:] if waivers else LABELS
    return [
        {
            "number": i,
            "label": label,
            "active": not done and i == step,
            "complete": done or i < step,
        }
        for i, label in enumerate(labels, 1)
    ]
