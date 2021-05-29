import React from 'react';
import { Typography } from '@material-ui/core';

class Auth extends React.Component {

    constructor(props) {
        super(props);

        this.state = {};
    };

    // begin authentication
    componentDidMount() {
        
        // access token is passed in the anchor field for some reason
        let queryString = window.location.hash.replace(/^#/, '?')
        let urlParams = new URLSearchParams(queryString)

        // use token to request project list
        if (urlParams.has('access_token')) {

            // finish authentication
            this.props.finishAuthentication(urlParams.get('access_token'))
        }

        // redirect to authentication screen if access token is not present
        else {
            let redirectUrl = window.ENV.OAUTH_ENDPOINT + '/oauth/authorize?'

            // parameters passed to OpenShift OAuth server
            let redirectParams = new URLSearchParams({
                client_id: window.ENV.OAUTH_CLIENT_ID,
                redirect_uri: window.location.origin,
                response_type: 'token'
            })

            // redirect to OAuth server
            window.location.replace(redirectUrl + redirectParams.toString())
        }
    }

    render() {

        return (
            <div>
                <Typography variant="subtitle2" color='textSecondary'>
                    Authenticating...
                </Typography>
            </div>
        )
    }

}

export default Auth;