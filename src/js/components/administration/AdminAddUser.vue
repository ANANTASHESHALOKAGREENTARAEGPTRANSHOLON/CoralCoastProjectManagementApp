<template>
    <div class="modal fade" id="addUserModal" data-bs-backdrop="static" data-bs-keyboard="false" tabindex="-1" aria-labelledby="addUserModalLabel" aria-hidden="true">
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title" id="addUserModalLabel">Add User</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <!-- Search Users -->
                    <div class="row"
                         v-if="destination !== 'user'"
                    >
                        <div class="col-md-4">
                            <strong>Search Users</strong>
                            <p class="text-instructions">
                                Please use the select to find the user you would like to add to this {{destination}}
                            </p>
                        </div>
                        <div class="col-md-8">
                            <label>Search User</label>
                            <v-select :options="userResults"
                                      v-model="userModel"
                                      class="form-control"
                            />
                        </div>
                    </div>
                    <hr v-if="destination !== 'user'">

                    <!-- Search Groups -->
                    <div class="row"
                         v-if="destination !== 'group'"
                    >
                        <div class="col-md-4">
                            <strong>Search Groups</strong>
                            <p class="text-instructions">
                                Please use the select to find the group you would like to add to this user to.
                            </p>
                        </div>
                        <div class="col-md-8">
                            <label>Search Groups</label>
                            <v-select :options="groupResults"
                                      v-model="groupModel"
                                      class="form-control"
                                      multiple
                            />
                        </div>
                    </div>
                    <hr v-if="destination !== 'group'">

                    <!-- Search Permission Sets -->
                    <div class="row"
                         v-if="destination !== 'permission_set'"
                    >
                        <div class="col-md-4">
                            <strong>Search Permission Sets</strong>
                            <p class="text-instructions">
                                Please use the select to find the permission set you would like to add to this user.
                            </p>
                        </div>
                        <div class="col-md-8">
                            <label>Search Permission Sets</label>
                            <v-select :options="permissionSetResults"
                                      v-model="permissionSetModel"
                                      class="form-control"
                                      multiple
                            />
                        </div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                    <button type="button" class="btn btn-primary" v-on:click="addUser">Add User</button>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
    const axios = require('axios');

    //VueX
    import { mapGetters } from 'vuex';

    //Import Mixins
    import errorModalMixin from "../../mixins/errorModalMixin";

    export default {
        name: "AdminAddUser",
        props: {
            destination: {
                type: String,
                default: "",
            },
            locationId: {
                type: Number,
                default: 0,
            },
        },
        data() {
            return {
                groupModel: [],
                groupResults: [],
                permissionSetModel: [],
                permissionSetResults: [],
                userModel: [],
                userResults: [],
            }
        },
        computed: {
            ...mapGetters({
                rootUrl: "getRootUrl",
                userLevel: "getUserLevel",
            }),
        },
        mixins: [
            errorModalMixin,
        ],
        methods: {
            addUser: function() {
                //Create the data_to_send
                const data_to_send = new FormData();
                data_to_send.set('username', this.userModel['value']);

                //Loop through all the groups
                this.groupModel.forEach(row => {
                    data_to_send.append('group', row['value']);
                });

                //Loop through all the permission_sets
                this.permissionSetModel.forEach(row => {
                    data_to_send.append('permission_set', row['value']);
                });

                axios.post(
                    `${this.rootUrl}admin_add_user/`,
                    data_to_send,
                ).then(response => {
                    //Just refresh the page (for now)
                    window.location.reload(true);
                }).catch(error => {
                    this.showErrorModal(error, 'Admin Add user', '');
                })
            },
            getData: function() {
                //Use Axios to obtain all the group, permission-set, and user results
                axios.post(
                    `${this.rootUrl}object_data/admin_add_user/`,
                ).then(response => {
                    //Assign it to the appropriate variable
                    this.groupResults = response['data']['group_results'].map(data => {
                        return {
                            'label': data['group_name'],
                            'value': data['group_id'],
                        }
                    });

                    this.permissionSetResults = response['data']['permission_set_results'].map(data => {
                        return {
                            'label': data['permission_set_name'],
                            'value': data['permission_set_id'],
                        }
                    });

                    this.userResults = response['data']['user_results'].map(data => {
                        return {
                            'label': `${data['id']}: ${data['first_name']} ${data['last_name']}`,
                            'value': data['id'],
                        }
                    });

                    //Use a simple if statement to find out which destination we are concentrating on
                    //Then filter the responses of that destination to determine the modal response
                    switch(this.destination) {
                        case "group":
                            //Filter group model data from group results
                            this.groupModel = this.groupResults.filter(row => {
                                return row['value'] === this.locationId;
                            });
                            break;
                        case "permission_set":
                            //Filter permission set model data from permission set results
                            this.permissionSetModel = this.permissionSetResults.filter(row => {
                                return row['value'] === this.locationId;
                            });
                            break;
                        case "user":
                            //Filter user model data from user results
                            this.userModel = this.userResults.filter(row => {
                                return row['value'] === this.locationId;
                            })[0];
                            break;
                        default:
                            break;
                    }
                }).catch(error => {
                    this.showErrorModal(error, 'Admin Add User', '');
                })
            },
        },
        mounted() {
            //Form loads - obtain data.
            this.getData();
        }
    }
</script>

<style scoped>

</style>
