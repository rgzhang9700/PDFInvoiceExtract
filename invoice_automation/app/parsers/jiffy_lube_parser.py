from .generic_parser import GenericParser


class JiffyLubeParser(GenericParser):
    """Fallback parser for Jiffy Lube / MyFleetCenter invoice PDFs."""

    def _find_vendor_name(self, text):
        upper_text = (text or "").upper()
        if "MYFLEETCENTER" in upper_text or "MY FLEET CENTER" in upper_text:
            return "MyFleetCenter"
        return "Jiffy Lube"
