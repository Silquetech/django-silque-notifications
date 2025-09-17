from silque.contrib.simple_history.admin import SimpleHistoryAdmin


class SilqueModelAdmin(SimpleHistoryAdmin):
    class Meta:
        abstract = True
        readonly_fields = [
            "created", "updated",
        ]
        exclude = [
            "tags", "attachments"
        ]
        
    def get_exclude(self, request, obj=None):
        if self.exclude:
            return list(self.exclude) + self.Meta.exclude
        
        return self.Meta.exclude

    def get_readonly_fields(self, request, obj=None):
        # readonly_fields = super().get_readonly_fields(request, obj)
        # print('Super: ', readonly_fields)
        # print('Meta: ', self.Meta.readonly_fields)
        # if obj is not None:
        #     readonly_fields += obj._meta.readonly_fields
        # return readonly_fields
        
        readonly_fields = super().get_readonly_fields(request, obj)
        if self.Meta.readonly_fields:
            readonly_fields = list(readonly_fields) + self.Meta.readonly_fields
            
        return readonly_fields