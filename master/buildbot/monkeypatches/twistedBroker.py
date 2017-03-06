from twisted.spread.pb import Broker
from twisted.python import log


def patch_proto_decref():
    """
    Patch proto_decref
    We are calling to make sure objects gets clean up
    """
    broker_proto_decref = Broker.proto_decref

    def proto_decref(self, objectID):
        """(internal) Decrement the reference count of an object.

        If the reference count is zero, it will free the reference to this
        object.
        """
        obj = self.localObjects.get(objectID)
        processUniqueID = obj and self.localObjects[objectID].object.processUniqueID()

        if processUniqueID and processUniqueID in self.luids:
            broker_proto_decref(self, objectID)

    Broker.proto_decref = proto_decref
