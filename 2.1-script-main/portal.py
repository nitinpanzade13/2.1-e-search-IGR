from session import create_session, open_portal
from form_parser import get_hidden_fields
from config import BASE_URL


class IGRPortal:

    def __init__(self):
        self.session = create_session()
        self.html = ""

    def open(self):
        print("Opening IGR portal...")

        self.html = open_portal(self.session)

        print("Initial HTML received.")
        print("Hidden fields:")

        fields = get_hidden_fields(self.html)

        for key, value in fields.items():
            print(f"  {key}: {len(value)} characters")

        return self.html

    def switch_to_rest_of_maharashtra(self):
        """
        The portal requires the 'Rest of Maharashtra' tab/postback
        before the district list becomes available.

        This method only prepares the POST request.
        """

        fields = get_hidden_fields(self.html)

        data = {
            "__EVENTTARGET": "",
            "__EVENTARGUMENT": "",
            "__LASTFOCUS": "",

            **fields,

            "btnOtherdistrictSearch":
                "Rest of Maharashtra / उर्वरित महाराष्ट्र",
        }

        print("Sending tab-switch request...")

        response = self.session.post(
            BASE_URL + "/",
            data=data,
            timeout=90
        )

        response.raise_for_status()

        self.html = response.text

        print("Tab-switch response received.")
        print("Status:", response.status_code)
        print("Response size:", len(response.text), "characters")

        return self.html


if __name__ == "__main__":

    portal = IGRPortal()

    portal.open()

    portal.switch_to_rest_of_maharashtra()